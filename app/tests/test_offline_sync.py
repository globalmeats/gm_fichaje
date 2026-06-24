"""Sincronización de fichajes offline sin pérdida ni duplicado (REQ-22). Requiere BD.

El evento offline conserva su hora real (`occurred_at` del cliente), el mismo `client_event_id`
no duplica (idempotente) y un `occurred_at` fuera de la ventana de tolerancia se rechaza.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from sqlalchemy import func, select

from app.core.security import create_access_token
from app.core.time import utc_now
from app.db.models import TimeRecord
from app.services.onboarding import create_employee


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_offline_event_keeps_real_time(client, db):
    w = await create_employee(db, "Off", "Line")
    h = _auth(create_access_token(w.id, "empleado", pin_temporary=False))

    real = (utc_now() - timedelta(hours=3)).replace(microsecond=0)
    r = await client.post(
        "/fichaje/sync",
        json={
            "event_type": "check_in",
            "occurred_at": real.isoformat(),
            "client_event_id": "evt-1",
        },
        headers=h,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["deduplicated"] is False
    # occurred_at = hora REAL del cliente.
    assert datetime.fromisoformat(body["occurred_at"]) == real

    # created_at (hora del servidor) es reciente y distinta de occurred_at.
    rec = (
        await db.execute(select(TimeRecord).where(TimeRecord.worker_id == w.id))
    ).scalar_one()
    assert rec.source == "offline_sync"
    assert rec.client_event_id == "evt-1"
    assert rec.created_at > real


async def test_offline_idempotent_no_duplicate(client, db):
    w = await create_employee(db, "Idem", "Potent")
    h = _auth(create_access_token(w.id, "empleado", pin_temporary=False))

    real = (utc_now() - timedelta(hours=1)).replace(microsecond=0)
    payload = {
        "event_type": "check_in",
        "occurred_at": real.isoformat(),
        "client_event_id": "dup-key",
    }

    r1 = await client.post("/fichaje/sync", json=payload, headers=h)
    assert r1.status_code == 201
    assert r1.json()["deduplicated"] is False

    # Reenvío del MISMO evento (reintento de la cola): no duplica.
    r2 = await client.post("/fichaje/sync", json=payload, headers=h)
    assert r2.status_code == 201
    assert r2.json()["deduplicated"] is True
    assert r2.json()["id"] == r1.json()["id"]

    count = (
        await db.execute(
            select(func.count()).select_from(TimeRecord).where(TimeRecord.worker_id == w.id)
        )
    ).scalar_one()
    assert count == 1


async def test_offline_future_rejected(client, db):
    w = await create_employee(db, "Fut", "Uro")
    h = _auth(create_access_token(w.id, "empleado", pin_temporary=False))

    future = utc_now() + timedelta(hours=1)
    r = await client.post(
        "/fichaje/sync",
        json={
            "event_type": "check_in",
            "occurred_at": future.isoformat(),
            "client_event_id": "evt-future",
        },
        headers=h,
    )
    assert r.status_code == 422


async def test_offline_too_old_rejected(client, db):
    w = await create_employee(db, "Vie", "Jo")
    h = _auth(create_access_token(w.id, "empleado", pin_temporary=False))

    too_old = utc_now() - timedelta(hours=200)  # > max_offline_age_hours (72 por defecto)
    r = await client.post(
        "/fichaje/sync",
        json={
            "event_type": "check_in",
            "occurred_at": too_old.isoformat(),
            "client_event_id": "evt-old",
        },
        headers=h,
    )
    assert r.status_code == 422


async def test_offline_invalid_transition_conflict(client, db):
    w = await create_employee(db, "Tra", "Ns")
    h = _auth(create_access_token(w.id, "empleado", pin_temporary=False))

    real = (utc_now() - timedelta(hours=1)).replace(microsecond=0)
    # check_out sin check_in previo: transición imposible.
    r = await client.post(
        "/fichaje/sync",
        json={
            "event_type": "check_out",
            "occurred_at": real.isoformat(),
            "client_event_id": "evt-bad",
        },
        headers=h,
    )
    assert r.status_code == 409


async def test_offline_chain_stays_valid(client, db):
    """Tras un evento offline (con geo/cid), la cadena del trabajador sigue verificándose."""
    from app.audit.chain import verify_chain

    w = await create_employee(db, "Cad", "Ena")
    h = _auth(create_access_token(w.id, "empleado", pin_temporary=False))

    real = (utc_now() - timedelta(hours=2)).replace(microsecond=0)
    await client.post(
        "/fichaje/sync",
        json={
            "event_type": "check_in",
            "occurred_at": real.isoformat(),
            "client_event_id": "chain-1",
        },
        headers=h,
    )
    # Evento online posterior encadena sobre el offline.
    await client.post("/fichaje/event", json={"event_type": "check_out"}, headers=h)

    ok, broken = await verify_chain(db, uuid.UUID(w.id))
    assert ok is True
    assert broken is None
