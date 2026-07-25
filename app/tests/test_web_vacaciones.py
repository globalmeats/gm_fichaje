"""Solicitud de vacaciones por el trabajador + aprobación/rechazo por administración (REQ-28)."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.core.security import create_access_token
from app.db.models import Absence
from app.services.onboarding import create_employee
from app.web.session import COOKIE_NAME


def _login(client, worker_id: str, role: str) -> None:
    client.cookies.set(COOKIE_NAME, create_access_token(worker_id, role, pin_temporary=False))


async def _one_absence(db, worker_id: str) -> Absence:
    q = select(Absence).where(Absence.worker_id == uuid.UUID(worker_id))
    return (await db.execute(q)).scalar_one()


async def test_trabajador_solicita_vacaciones_queda_pendiente(client, db):
    w = await create_employee(db, "Vera", "Sol")
    _login(client, w.id, "empleado")
    r = await client.post(
        "/mis-ausencias/solicitar",
        data={"start_date": "2026-08-10", "end_date": "2026-08-14", "note": "playa"},
    )
    assert r.status_code == 200
    assert "Pendiente de aprobación" in r.text
    a = await _one_absence(db, w.id)
    assert a.absence_type == "vacaciones" and a.status == "pendiente"


async def test_solicitud_solapada_se_rechaza(client, db):
    w = await create_employee(db, "Vera", "Dos")
    _login(client, w.id, "empleado")
    base = {"start_date": "2026-08-10", "end_date": "2026-08-14"}
    await client.post("/mis-ausencias/solicitar", data=base)
    r = await client.post(
        "/mis-ausencias/solicitar",
        data={"start_date": "2026-08-12", "end_date": "2026-08-16"},
    )
    assert "solapa" in r.text.lower()


async def test_trabajador_cancela_su_solicitud_pendiente(client, db):
    w = await create_employee(db, "Vera", "Tres")
    _login(client, w.id, "empleado")
    await client.post(
        "/mis-ausencias/solicitar",
        data={"start_date": "2026-09-01", "end_date": "2026-09-03"},
    )
    a = await _one_absence(db, w.id)
    r = await client.post(f"/mis-ausencias/{a.id}/cancelar")
    assert r.status_code == 200
    await db.refresh(a)
    assert a.status == "cancelada"


async def test_admin_aprueba_solicitud(client, db):
    emp = await create_employee(db, "Emp", "Vac")
    admin = await create_employee(db, "Adm", "Vac", role="admin")
    _login(client, emp.id, "empleado")
    await client.post(
        "/mis-ausencias/solicitar",
        data={"start_date": "2026-10-05", "end_date": "2026-10-09"},
    )
    a = await _one_absence(db, emp.id)

    _login(client, admin.id, "admin")
    r = await client.post(f"/admin/ausencias/{a.id}/aprobar", follow_redirects=False)
    assert r.status_code == 303
    await db.refresh(a)
    assert a.status == "aprobada" and a.verified_by == uuid.UUID(admin.id)


async def test_admin_rechaza_solicitud(client, db):
    emp = await create_employee(db, "Emp", "Rec")
    admin = await create_employee(db, "Adm", "Rec", role="admin")
    _login(client, emp.id, "empleado")
    await client.post(
        "/mis-ausencias/solicitar",
        data={"start_date": "2026-11-02", "end_date": "2026-11-04"},
    )
    a = await _one_absence(db, emp.id)

    _login(client, admin.id, "admin")
    await client.post(f"/admin/ausencias/{a.id}/rechazar", follow_redirects=False)
    await db.refresh(a)
    assert a.status == "rechazada"


async def test_empleado_no_puede_aprobar(client, db):
    emp = await create_employee(db, "Emp", "NoAdm")
    other = await create_employee(db, "Otro", "Emp")
    _login(client, emp.id, "empleado")
    await client.post(
        "/mis-ausencias/solicitar",
        data={"start_date": "2026-12-01", "end_date": "2026-12-02"},
    )
    a = await _one_absence(db, emp.id)
    _login(client, other.id, "empleado")
    r = await client.post(f"/admin/ausencias/{a.id}/aprobar", follow_redirects=False)
    assert r.status_code == 403
