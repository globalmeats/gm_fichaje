"""Alerta de tope anual de jornada (REQ-27). Requiere BD.

Si el trabajador supera su tope anual, un fichaje deja una alerta `annual_cap` (sin bloquear),
y no se duplica dentro del mismo año.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from app.audit.chain import append_event
from app.core.security import create_access_token
from app.db.models import AuditAlert, Worker
from app.services.onboarding import create_employee


def _today(h: int) -> datetime:
    return datetime.now(UTC).replace(hour=h, minute=0, second=0, microsecond=0)


def _auth(worker_id: str) -> dict[str, str]:
    token = create_access_token(worker_id, "empleado", pin_temporary=False)
    return {"Authorization": f"Bearer {token}"}


async def _eight_hour_journey(db, worker_id: uuid.UUID) -> None:
    await append_event(db, worker_id, "check_in", occurred_at=_today(9))
    await append_event(db, worker_id, "check_out", occurred_at=_today(17))


async def test_exceeding_cap_generates_alert(client, db):
    created = await create_employee(db, "Topa", "Anual")
    wid = uuid.UUID(created.id)
    worker = await db.get(Worker, wid)
    worker.annual_hours_cap = 4  # 8h trabajadas superan el tope de 4h
    await db.commit()

    await _eight_hour_journey(db, wid)

    # Un nuevo fichaje dispara la comprobación del tope (la jornada cerrada ya lo supera).
    r = await client.post(
        "/fichaje/event", json={"event_type": "check_in"}, headers=_auth(created.id)
    )
    assert r.status_code == 201, r.text

    alerts = (
        await db.execute(
            select(AuditAlert).where(
                AuditAlert.worker_id == wid, AuditAlert.alert_type == "annual_cap"
            )
        )
    ).scalars().all()
    assert len(alerts) == 1
    assert alerts[0].severity == "warning"


async def test_no_alert_under_cap(client, db):
    created = await create_employee(db, "Bajo", "Tope")
    wid = uuid.UUID(created.id)
    # Cap por defecto (1760h) muy por encima de una jornada de 8h.
    await _eight_hour_journey(db, wid)

    r = await client.post(
        "/fichaje/event", json={"event_type": "check_in"}, headers=_auth(created.id)
    )
    assert r.status_code == 201, r.text

    alerts = (
        await db.execute(
            select(AuditAlert).where(
                AuditAlert.worker_id == wid, AuditAlert.alert_type == "annual_cap"
            )
        )
    ).scalars().all()
    assert alerts == []
