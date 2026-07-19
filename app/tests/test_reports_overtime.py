"""Reporte de horas extra por periodo (REQ-08, REQ-12). Requiere BD.

GET /reports/overtime: propio por defecto; supervisión puede ver a otro; empleado no.
"""

from __future__ import annotations

from app.core.security import create_access_token
from app.services.onboarding import create_employee


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _post(client, h, event_type, **extra):
    return await client.post(
        "/fichaje/event", json={"event_type": event_type, **extra}, headers=h
    )


async def test_overtime_report_own(client, db):
    w = await create_employee(db, "Over", "Time")
    h = _auth(create_access_token(w.id, "empleado", pin_temporary=False))

    await _post(client, h, "check_in")
    await _post(client, h, "check_out")

    r = await client.get("/reports/overtime", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["worker_id"] == str(w.id)
    assert body["period"] in ("daily", "weekly", "monthly")
    assert body["efectivo_min"] >= 0
    assert body["ordinarias_min"] + body["extra_min"] == body["efectivo_min"]
    assert body["compensacion"] == "pending"


async def test_oversight_can_query_other_worker(client, db):
    sup = await create_employee(db, "Sup", "Ervisor", role="supervisor")
    emp = await create_employee(db, "Sub", "Ordinado")
    hs = _auth(create_access_token(sup.id, "supervisor", pin_temporary=False))

    r = await client.get(f"/reports/overtime?worker_id={emp.id}", headers=hs)
    assert r.status_code == 200, r.text
    assert r.json()["worker_id"] == str(emp.id)


async def test_employee_cannot_query_other_worker(client, db):
    e1 = await create_employee(db, "Em", "Uno")
    e2 = await create_employee(db, "Em", "Dos")
    h1 = _auth(create_access_token(e1.id, "empleado", pin_temporary=False))

    r = await client.get(f"/reports/overtime?worker_id={e2.id}", headers=h1)
    assert r.status_code == 403
