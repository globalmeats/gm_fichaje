"""BUG-05: los escaneos acotados dan el mismo resultado que cargar todo el histórico."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.api.fichaje import _ordered_event_types
from app.audit.chain import append_event
from app.core.security import create_access_token
from app.domain.state_machine import State, reconstruct_state
from app.services.onboarding import create_employee


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_ordered_event_types_solo_jornada_abierta(db):
    """Tras varias jornadas cerradas, el estado acotado = estado del histórico completo."""
    w = await create_employee(db, "Bug", "Cinco")
    wid = uuid.UUID(w.id)
    # Dos jornadas completas + una tercera abierta con pausa.
    for ev in ("check_in", "check_out", "check_in", "check_out", "check_in", "break_start"):
        await append_event(db, wid, ev)

    bounded = await _ordered_event_types(db, wid)
    # Solo debe traer los eventos posteriores al último check_out: check_in + break_start.
    assert bounded == ["check_in", "break_start"]
    assert reconstruct_state(bounded) == State.EN_PAUSA


async def test_ordered_event_types_idle_tras_checkout(db):
    w = await create_employee(db, "Bug", "Seis")
    wid = uuid.UUID(w.id)
    for ev in ("check_in", "check_out"):
        await append_event(db, wid, ev)
    bounded = await _ordered_event_types(db, wid)
    assert bounded == []
    assert reconstruct_state(bounded) == State.IDLE


async def test_annual_cap_alert_ignora_anio_anterior(client, db):
    """Una jornada del año pasado no cuenta para el tope de este año (query acotada por año)."""
    w = await create_employee(db, "Bug", "Anual")
    wid = uuid.UUID(w.id)
    # Jornada del año anterior (no debe contar). occurred_at se sella con esta hora.
    prev = datetime(datetime.now(UTC).year - 1, 6, 1, 9, tzinfo=UTC)
    await append_event(db, wid, "check_in", occurred_at=prev)
    await append_event(
        db, wid, "check_out", occurred_at=prev.replace(hour=17), client_event_id="prev-out"
    )
    # Un fichaje de hoy vía API: dispara _alert_if_annual_cap con la query acotada; no debe romper.
    token = create_access_token(w.id, "empleado", pin_temporary=False)
    r = await client.post("/fichaje/event", json={"event_type": "check_in"}, headers=_auth(token))
    assert r.status_code == 201
