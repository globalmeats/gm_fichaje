"""Tests del bloque de críticos de la auditoría 2026-07 (BUG-01, SEC-01, SEC-05)."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from app.audit.chain import append_event, verify_chain
from app.domain.state_machine import InvalidTransition, State, reconstruct_state
from app.services.onboarding import create_employee

# ---- BUG-01: validación de estado atómica bajo el lock ----


async def test_append_event_valida_transicion_bajo_lock(db):
    created = await create_employee(db, "Bug", "Uno")
    wid = uuid.UUID(created.id)

    def _reject_double_checkin(types: list[str]) -> None:
        from app.domain.state_machine import next_state

        next_state(reconstruct_state(types), "check_in")

    await append_event(db, wid, "check_in", validate_transition=_reject_double_checkin)
    # Segundo check_in: el validador (bajo lock) debe rechazarlo.
    with pytest.raises(InvalidTransition):
        await append_event(db, wid, "check_in", validate_transition=_reject_double_checkin)

    ok, bad = await verify_chain(db, wid)
    assert ok, f"cadena rota en {bad}"


async def test_fichaje_event_doble_checkin_devuelve_409(client, db):
    created = await create_employee(db, "Bug", "Api")
    from app.core.security import create_access_token

    token = create_access_token(worker_id=created.id, role="empleado", pin_temporary=False)
    h = {"Authorization": f"Bearer {token}"}

    r1 = await client.post("/fichaje/event", json={"event_type": "check_in"}, headers=h)
    assert r1.status_code == 201
    r2 = await client.post("/fichaje/event", json={"event_type": "check_in"}, headers=h)
    assert r2.status_code == 409


def test_reconstruct_state_no_estricto_no_lanza():
    # Histórico incoherente (dos check_in): estricto lanza, defensivo no.
    with pytest.raises(InvalidTransition):
        reconstruct_state(["check_in", "check_in"], strict=True)
    # No revienta y devuelve un estado utilizable (lectura defensiva).
    assert reconstruct_state(["check_in", "check_in"], strict=False) == State.ABIERTA


async def test_today_no_500_con_historico_incoherente(client, db):
    """Aunque el histórico fuese incoherente, /today no debe caer a 500 (BUG-01)."""
    created = await create_employee(db, "Bug", "Read")
    wid = uuid.UUID(created.id)
    # Inserta dos check_in saltándose el validador (simula un histórico corrupto heredado).
    await append_event(db, wid, "check_in")
    await append_event(db, wid, "check_in")

    from app.core.security import create_access_token

    token = create_access_token(worker_id=created.id, role="empleado", pin_temporary=False)
    r = await client.get("/fichaje/today", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200


# ---- SEC-05: TRUNCATE bloqueado en tablas inmutables ----


async def test_truncate_time_record_bloqueado(db):
    created = await create_employee(db, "Sec", "Cinco")
    await append_event(db, uuid.UUID(created.id), "check_in")
    with pytest.raises(Exception) as exc:
        await db.execute(text("TRUNCATE time_record"))
    await db.rollback()
    assert "append-only" in str(exc.value).lower() or "truncate" in str(exc.value).lower()
