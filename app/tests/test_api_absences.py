"""API de ausencias y justificantes (REQ-28). Requiere BD.

Alta/gestión solo admin/gestora; el trabajador consulta lo suyo y descarga su justificante.
El justificante se guarda cifrado y nunca aparece en los listados JSON.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.core.security import create_access_token
from app.db.models import AbsenceDocument
from app.services.onboarding import create_employee


def _auth(worker_id: str, role: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(worker_id, role, pin_temporary=False)}"}


def _vac_body(worker_id: str, start: str, end: str) -> dict:
    return {
        "worker_id": worker_id,
        "absence_type": "vacaciones",
        "start_date": start,
        "end_date": end,
    }


async def test_admin_creates_absence(client, db):
    admin = await create_employee(db, "Adm", "Aus", role="admin")
    w = await create_employee(db, "Tra", "Bajador")
    h = _auth(admin.id, "admin")

    r = await client.post("/absences", json=_vac_body(w.id, "2026-07-06", "2026-07-10"), headers=h)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["absence_type"] == "vacaciones"
    assert body["has_document"] is False
    assert body["status"] == "aprobada"


async def test_employee_cannot_create_absence(client, db):
    w = await create_employee(db, "Em", "Pleado")
    h = _auth(w.id, "empleado")
    r = await client.post("/absences", json=_vac_body(w.id, "2026-07-06", "2026-07-10"), headers=h)
    assert r.status_code == 403


async def test_overlapping_absence_rejected(client, db):
    admin = await create_employee(db, "Adm", "Solape", role="admin")
    w = await create_employee(db, "Tra", "Solape")
    h = _auth(admin.id, "admin")

    r1 = await client.post(
        "/absences", json=_vac_body(w.id, "2026-07-06", "2026-07-10"), headers=h
    )
    assert r1.status_code == 201, r1.text
    r2 = await client.post(
        "/absences", json=_vac_body(w.id, "2026-07-09", "2026-07-12"), headers=h
    )
    assert r2.status_code == 422


async def test_permiso_requires_valid_subtype(client, db):
    admin = await create_employee(db, "Adm", "Permiso", role="admin")
    w = await create_employee(db, "Tra", "Permiso")
    h = _auth(admin.id, "admin")
    bad = {
        "worker_id": w.id,
        "absence_type": "permiso",
        "subtype": "inventado",
        "start_date": "2026-07-06",
        "end_date": "2026-07-06",
    }
    r = await client.post("/absences", json=bad, headers=h)
    assert r.status_code == 422


async def test_employee_lists_own_not_others(client, db):
    admin = await create_employee(db, "Adm", "List", role="admin")
    w = await create_employee(db, "Pro", "Pio")
    other = await create_employee(db, "Aje", "No")
    await client.post(
        "/absences", json=_vac_body(w.id, "2026-07-06", "2026-07-10"),
        headers=_auth(admin.id, "admin"),
    )

    own = await client.get("/absences", headers=_auth(w.id, "empleado"))
    assert own.status_code == 200
    assert len(own.json()) == 1

    blocked = await client.get(
        f"/absences?worker_id={other.id}", headers=_auth(w.id, "empleado")
    )
    assert blocked.status_code == 403


async def test_cancel_absence(client, db):
    admin = await create_employee(db, "Adm", "Cancel", role="admin")
    w = await create_employee(db, "Tra", "Cancel")
    h = _auth(admin.id, "admin")
    created = await client.post(
        "/absences", json=_vac_body(w.id, "2026-07-06", "2026-07-10"), headers=h
    )
    aid = created.json()["id"]

    r = await client.post(f"/absences/{aid}/cancel", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "cancelada"


async def test_upload_and_download_justificante(client, db):
    admin = await create_employee(db, "Adm", "Just", role="admin")
    w = await create_employee(db, "Tra", "Just")
    h = _auth(admin.id, "admin")
    created = await client.post(
        "/absences", json=_vac_body(w.id, "2026-07-06", "2026-07-10"), headers=h
    )
    aid = created.json()["id"]

    data = b"%PDF-1.4 fake asistencia"
    up = await client.post(
        f"/absences/{aid}/justificante",
        files={"file": ("asistencia.pdf", data, "application/pdf")},
        headers=h,
    )
    assert up.status_code == 201, up.text
    doc_id = up.json()["id"]
    assert up.json()["content_type"] == "application/pdf"

    # Se guarda cifrado: el bytea en BD no es el texto plano.
    stored = (
        await db.execute(
            select(AbsenceDocument).where(AbsenceDocument.id == uuid.UUID(doc_id))
        )
    ).scalar_one()
    assert stored.content_encrypted != data

    # La ausencia queda marcada como justificada y aparece has_document en el listado.
    listed = await client.get("/absences", headers=_auth(w.id, "empleado"))
    item = listed.json()[0]
    assert item["justified"] is True
    assert item["has_document"] is True

    # El propio trabajador descarga su justificante (texto plano descifrado).
    dl = await client.get(
        f"/absences/{aid}/justificante/{doc_id}", headers=_auth(w.id, "empleado")
    )
    assert dl.status_code == 200
    assert dl.content == data


async def test_upload_rejects_bad_content_type(client, db):
    admin = await create_employee(db, "Adm", "Tipo", role="admin")
    w = await create_employee(db, "Tra", "Tipo")
    h = _auth(admin.id, "admin")
    created = await client.post(
        "/absences", json=_vac_body(w.id, "2026-07-06", "2026-07-10"), headers=h
    )
    aid = created.json()["id"]
    up = await client.post(
        f"/absences/{aid}/justificante",
        files={"file": ("informe.txt", b"texto", "text/plain")},
        headers=h,
    )
    assert up.status_code == 422


async def test_download_blocked_for_other_employee(client, db):
    admin = await create_employee(db, "Adm", "Down", role="admin")
    w = await create_employee(db, "Due", "Nyo")
    other = await create_employee(db, "Aje", "Down")
    h = _auth(admin.id, "admin")
    created = await client.post(
        "/absences", json=_vac_body(w.id, "2026-07-06", "2026-07-10"), headers=h
    )
    aid = created.json()["id"]
    up = await client.post(
        f"/absences/{aid}/justificante",
        files={"file": ("a.pdf", b"%PDF data", "application/pdf")},
        headers=h,
    )
    doc_id = up.json()["id"]

    r = await client.get(
        f"/absences/{aid}/justificante/{doc_id}", headers=_auth(other.id, "empleado")
    )
    # Bloqueado: 403 (capa de app) o 404 (con RLS el registro ajeno ni es visible).
    assert r.status_code in (403, 404)


async def test_vacation_balance(client, db):
    admin = await create_employee(db, "Adm", "Bal", role="admin")
    w = await create_employee(db, "Tra", "Bal")
    # 5 días laborables de vacaciones este año.
    from app.core.time import utc_now

    year = utc_now().year
    await client.post(
        "/absences",
        json=_vac_body(w.id, f"{year}-07-06", f"{year}-07-10"),
        headers=_auth(admin.id, "admin"),
    )
    r = await client.get("/absences/me/balance", headers=_auth(w.id, "empleado"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["year"] == year
    assert body["taken"] == 5
    assert body["remaining"] == body["entitled"] - 5
