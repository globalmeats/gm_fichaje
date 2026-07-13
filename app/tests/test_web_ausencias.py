"""Frontend SSR — ausencias en el panel y portal del trabajador (Fase 8, REQ-28).

El alta/gestión de ausencias y la subida de justificantes son SOLO admin/gestora. El trabajador
consulta lo suyo y su saldo de vacaciones en «Mis ausencias» y descarga su propio justificante.
"""

from __future__ import annotations

from app.core.security import create_access_token
from app.core.time import utc_now
from app.services.onboarding import create_employee
from app.web.session import COOKIE_NAME


async def _session(client, role: str, worker_id: str) -> None:
    token = create_access_token(worker_id, role, pin_temporary=False)
    client.cookies.set(COOKIE_NAME, token)


async def test_empleado_forbidden_in_admin_ausencias(client, db):
    w = await create_employee(db, "Em", "Pleado")
    await _session(client, "empleado", w.id)
    r = await client.get("/admin/ausencias", follow_redirects=False)
    assert r.status_code == 403


async def test_admin_creates_vacation(client, db):
    admin = await create_employee(db, "Adm", "Web", role="admin")
    w = await create_employee(db, "Tra", "Web")
    await _session(client, "admin", admin.id)

    year = utc_now().year
    r = await client.post(
        "/admin/ausencias",
        data={
            "worker_id": str(w.id),
            "absence_type": "vacaciones",
            "start_date": f"{year}-08-03",
            "end_date": f"{year}-08-07",
        },
    )
    assert r.status_code == 200, r.text
    assert "Ausencia registrada" in r.text
    assert "vacaciones" in r.text


async def test_admin_creates_hourly_permiso(client, db):
    admin = await create_employee(db, "Adm", "Hora", role="admin")
    w = await create_employee(db, "Tra", "Hora")
    await _session(client, "admin", admin.id)

    year = utc_now().year
    r = await client.post(
        "/admin/ausencias",
        data={
            "worker_id": str(w.id),
            "absence_type": "permiso",
            "subtype": "deber_inexcusable",
            "start_date": f"{year}-08-10",
            "end_date": f"{year}-08-10",
            "start_time": "09:00",
            "end_time": "11:00",
        },
    )
    assert r.status_code == 200, r.text
    assert "Ausencia registrada" in r.text


async def test_admin_invalid_permiso_subtype_shows_error(client, db):
    admin = await create_employee(db, "Adm", "Bad", role="admin")
    w = await create_employee(db, "Tra", "Bad")
    await _session(client, "admin", admin.id)

    year = utc_now().year
    r = await client.post(
        "/admin/ausencias",
        data={
            "worker_id": str(w.id),
            "absence_type": "permiso",
            "subtype": "inventado",
            "start_date": f"{year}-08-12",
            "end_date": f"{year}-08-12",
        },
    )
    assert r.status_code == 200
    assert "no válidos" in r.text


async def test_upload_and_download_justificante_web(client, db):
    admin = await create_employee(db, "Adm", "Just", role="admin")
    w = await create_employee(db, "Tra", "Just")
    await _session(client, "admin", admin.id)

    year = utc_now().year
    await client.post(
        "/admin/ausencias",
        data={
            "worker_id": str(w.id),
            "absence_type": "vacaciones",
            "start_date": f"{year}-09-01",
            "end_date": f"{year}-09-03",
        },
    )
    page = await client.get(f"/admin/ausencias?worker_id={w.id}")
    assert page.status_code == 200

    from sqlalchemy import select

    from app.db.models import Absence

    absence = (
        await db.execute(select(Absence).where(Absence.worker_id == w.id))
    ).scalar_one()

    data = b"%PDF-1.4 asistencia"
    up = await client.post(
        f"/admin/ausencias/{absence.id}/justificante",
        files={"file": ("asistencia.pdf", data, "application/pdf")},
    )
    assert up.status_code == 200, up.text
    assert "Justificante subido" in up.text
    assert "/descargar/justificante/" in up.text

    from app.db.models import AbsenceDocument

    doc = (
        await db.execute(select(AbsenceDocument).where(AbsenceDocument.absence_id == absence.id))
    ).scalar_one()
    # Se guarda cifrado.
    assert doc.content_encrypted != data

    # El propio trabajador descarga su justificante (cookie-auth), descifrado.
    await _session(client, "empleado", w.id)
    dl = await client.get(f"/descargar/justificante/{absence.id}/{doc.id}")
    assert dl.status_code == 200
    assert dl.content == data


async def test_download_justificante_blocked_for_other(client, db):
    admin = await create_employee(db, "Adm", "Blk", role="admin")
    w = await create_employee(db, "Due", "Blk")
    other = await create_employee(db, "Aje", "Blk")
    await _session(client, "admin", admin.id)

    year = utc_now().year
    await client.post(
        "/admin/ausencias",
        data={
            "worker_id": str(w.id),
            "absence_type": "vacaciones",
            "start_date": f"{year}-09-10",
            "end_date": f"{year}-09-12",
        },
    )
    from sqlalchemy import select

    from app.db.models import Absence

    absence = (
        await db.execute(select(Absence).where(Absence.worker_id == w.id))
    ).scalar_one()
    await client.post(
        f"/admin/ausencias/{absence.id}/justificante",
        files={"file": ("a.pdf", b"%PDF data", "application/pdf")},
    )
    from app.db.models import AbsenceDocument

    doc = (
        await db.execute(select(AbsenceDocument).where(AbsenceDocument.absence_id == absence.id))
    ).scalar_one()

    await _session(client, "empleado", other.id)
    r = await client.get(
        f"/descargar/justificante/{absence.id}/{doc.id}", follow_redirects=False
    )
    assert r.status_code == 403


async def test_cancel_absence_web(client, db):
    admin = await create_employee(db, "Adm", "Can", role="admin")
    w = await create_employee(db, "Tra", "Can")
    await _session(client, "admin", admin.id)

    year = utc_now().year
    await client.post(
        "/admin/ausencias",
        data={
            "worker_id": str(w.id),
            "absence_type": "vacaciones",
            "start_date": f"{year}-10-01",
            "end_date": f"{year}-10-03",
        },
    )
    from sqlalchemy import select

    from app.db.models import Absence

    absence = (
        await db.execute(select(Absence).where(Absence.worker_id == w.id))
    ).scalar_one()
    r = await client.post(
        f"/admin/ausencias/{absence.id}/cancelar", follow_redirects=False
    )
    assert r.status_code == 303
    await db.refresh(absence)
    assert absence.status == "cancelada"


async def test_portal_mis_ausencias_shows_balance(client, db):
    admin = await create_employee(db, "Adm", "Por", role="admin")
    w = await create_employee(db, "Tra", "Por")
    await _session(client, "admin", admin.id)

    year = utc_now().year
    await client.post(
        "/admin/ausencias",
        data={
            "worker_id": str(w.id),
            "absence_type": "vacaciones",
            "start_date": f"{year}-11-02",
            "end_date": f"{year}-11-06",
        },
    )

    await _session(client, "empleado", w.id)
    r = await client.get("/mis-ausencias")
    assert r.status_code == 200
    assert "Saldo de vacaciones" in r.text
    assert "Tope anual de jornada" in r.text
    assert "vacaciones" in r.text
