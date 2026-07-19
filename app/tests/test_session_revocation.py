"""SEC-06/BUG-04: revocación de sesión por token_version, is_active y trabajo constante."""

from __future__ import annotations

import uuid

from sqlalchemy import text

from app.core.security import create_access_token
from app.services.onboarding import create_employee


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_stale_token_version_is_rejected(client, db):
    emp = await create_employee(db, "Rev", "Uno")
    # Token con la tv actual (0): funciona.
    ok = create_access_token(emp.id, "empleado", pin_temporary=False, token_version=0)
    r = await client.get("/fichaje/today", headers=_auth(ok))
    assert r.status_code == 200

    # Se incrementa token_version en BD (simula reset de PIN / bloqueo).
    await db.execute(
        text("UPDATE worker SET token_version = token_version + 1 WHERE id = :i"),
        {"i": uuid.UUID(emp.id)},
    )
    await db.commit()

    # El token viejo (tv=0) ya no vale.
    r = await client.get("/fichaje/today", headers=_auth(ok))
    assert r.status_code == 401


async def test_inactive_worker_token_rejected(client, db):
    emp = await create_employee(db, "Rev", "Dos")
    token = create_access_token(emp.id, "empleado", pin_temporary=False)
    await db.execute(
        text("UPDATE worker SET is_active = false WHERE id = :i"), {"i": uuid.UUID(emp.id)}
    )
    await db.commit()
    r = await client.get("/fichaje/today", headers=_auth(token))
    assert r.status_code == 401


async def test_reset_pin_revokes_active_session(client, db):
    admin = await create_employee(db, "Adm", "Rev", role="admin")
    emp = await create_employee(db, "Vic", "Tima")
    emp_token = create_access_token(emp.id, "empleado", pin_temporary=False)
    # Sesión del empleado válida.
    assert (await client.get("/fichaje/today", headers=_auth(emp_token))).status_code == 200

    # El admin resetea su PIN → debe invalidar la sesión activa del empleado.
    ha = _auth(create_access_token(admin.id, "admin", pin_temporary=False))
    r = await client.post(f"/admin/workers/{emp.id}/reset-pin", headers=ha)
    assert r.status_code == 200
    assert (await client.get("/fichaje/today", headers=_auth(emp_token))).status_code == 401


async def test_login_with_nonexistent_worker_uses_constant_work(client, db):
    # Código inexistente: 401 uniforme (y por dentro hace el verify_pin dummy, SEC-03).
    r = await client.post("/auth/login", json={"employee_code": "ZzZz", "pin": "123456"})
    assert r.status_code == 401
