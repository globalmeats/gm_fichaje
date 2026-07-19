"""SEC-01: nadie resetea el PIN de una cuenta de rol igual o superior al suyo."""

from __future__ import annotations

from app.api.deps import can_manage_account
from app.core.security import create_access_token
from app.services.onboarding import create_employee


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_can_manage_account_matrix():
    assert can_manage_account("admin", "empleado")
    assert can_manage_account("admin", "supervisor")
    assert can_manage_account("supervisor", "empleado")
    # Igual o superior: prohibido.
    assert not can_manage_account("supervisor", "admin")
    assert not can_manage_account("supervisor", "supervisor")
    assert not can_manage_account("admin", "admin")
    assert not can_manage_account("empleado", "empleado")


async def test_supervisor_cannot_reset_admin(client, db):
    admin = await create_employee(db, "Jefe", "Total", role="admin")
    sup = await create_employee(db, "Sup", "Ervisor", role="supervisor")
    h = _auth(create_access_token(sup.id, "supervisor", pin_temporary=False))

    r = await client.post(f"/admin/workers/{admin.id}/reset-pin", headers=h)
    assert r.status_code == 403, r.text


async def test_admin_can_reset_employee(client, db):
    admin = await create_employee(db, "Jefa", "Manda", role="admin")
    emp = await create_employee(db, "Curro", "Obrero")
    h = _auth(create_access_token(admin.id, "admin", pin_temporary=False))

    r = await client.post(f"/admin/workers/{emp.id}/reset-pin", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["pin_temporary"] is True


async def test_supervisor_can_reset_employee(client, db):
    sup = await create_employee(db, "Sup", "Dos", role="supervisor")
    emp = await create_employee(db, "Otro", "Curro")
    h = _auth(create_access_token(sup.id, "supervisor", pin_temporary=False))

    r = await client.post(f"/admin/workers/{emp.id}/reset-pin", headers=h)
    assert r.status_code == 200, r.text
