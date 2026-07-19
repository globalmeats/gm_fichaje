"""Política de tiempo configurable en runtime (REQ-13). Requiere BD.

GET/PUT /admin/time-policy: admin edita el singleton; los no-admin no pueden.
"""

from __future__ import annotations

from app.core.security import create_access_token
from app.services.onboarding import create_employee


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_get_time_policy_defaults(client, db):
    w = await create_employee(db, "Pol", "Icy", role="admin")
    h = _auth(create_access_token(w.id, "admin", pin_temporary=False))

    r = await client.get("/admin/time-policy", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["pause_computable_default"] is True
    assert body["computation_period"] == "monthly"


async def test_admin_updates_policy(client, db):
    w = await create_employee(db, "Edit", "Pol", role="admin")
    h = _auth(create_access_token(w.id, "admin", pin_temporary=False))

    r = await client.put(
        "/admin/time-policy",
        json={"pause_computable_default": False, "computation_period": "weekly"},
        headers=h,
    )
    assert r.status_code == 200, r.text
    assert r.json()["pause_computable_default"] is False

    # Persistido: un GET posterior lo refleja.
    r = await client.get("/admin/time-policy", headers=h)
    assert r.json()["pause_computable_default"] is False
    assert r.json()["computation_period"] == "weekly"


async def test_non_admin_cannot_update_policy(client, db):
    w = await create_employee(db, "No", "Admin")
    h = _auth(create_access_token(w.id, "empleado", pin_temporary=False))

    r = await client.put(
        "/admin/time-policy",
        json={"pause_computable_default": False},
        headers=h,
    )
    assert r.status_code == 403


async def test_policy_change_reflected_in_summary(client, db):
    """Con la pausa NO computable, la misma pausa deja de restar (efectivo == bruto)."""
    admin = await create_employee(db, "Adm", "Sum", role="admin")
    ha = _auth(create_access_token(admin.id, "admin", pin_temporary=False))

    # Desactiva la computabilidad de pausas globalmente.
    r = await client.put(
        "/admin/time-policy",
        json={"pause_computable_default": False},
        headers=ha,
    )
    assert r.status_code == 200

    w = await create_employee(db, "Tra", "Baja")
    h = _auth(create_access_token(w.id, "empleado", pin_temporary=False))
    for ev in ("check_in", "break_start", "break_end", "check_out"):
        assert (
            await client.post("/fichaje/event", json={"event_type": ev}, headers=h)
        ).status_code == 201

    r = await client.get("/fichaje/summary", headers=h)
    body = r.json()["today"][0]
    # Pausa no computable → no se descuenta.
    assert body["pausa_computable_min"] == 0
    assert body["efectivo_min"] == body["bruto_min"]
