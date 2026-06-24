"""Geolocalización puntual con consentimiento y cifrado en reposo (REQ-20, REQ-23). Requiere BD.

Con consentimiento + modalidad móvil, la geo se almacena CIFRADA (la columna no es texto plano)
y se descifra en el export. Sin consentimiento (o sin móvil), la geo no se almacena.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.core.crypto import decrypt_geo
from app.core.security import create_access_token
from app.db.models import TimeRecord, Worker
from app.services.onboarding import create_employee


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _set_consent(db, worker_id: str, consent: bool) -> None:
    worker = await db.get(Worker, uuid.UUID(worker_id))
    worker.geo_consent = consent
    await db.commit()


async def _stored_geo(db, worker_id: str) -> str | None:
    rec = (
        await db.execute(
            select(TimeRecord)
            .where(TimeRecord.worker_id == uuid.UUID(worker_id))
            .order_by(TimeRecord.seq.desc())
            .limit(1)
        )
    ).scalar_one()
    return rec.geo


async def test_geo_stored_encrypted_with_consent_and_movil(client, db):
    w = await create_employee(db, "Geo", "Consent")
    await _set_consent(db, w.id, True)
    h = _auth(create_access_token(w.id, "empleado", pin_temporary=False))

    plain = "40.4168,-3.7038"
    r = await client.post(
        "/fichaje/event",
        json={"event_type": "check_in", "modalidad": "movil", "geo": plain},
        headers=h,
    )
    assert r.status_code == 201, r.text

    stored = await _stored_geo(db, w.id)
    # Cifrada en reposo: la columna NO contiene el texto plano.
    assert stored is not None
    assert stored != plain
    # Pero descifra al valor original.
    assert decrypt_geo(stored) == plain

    # El export la descifra para mostrarla.
    r = await client.get("/me/records", headers=h)
    assert r.status_code == 200
    geos = [row["geo"] for row in r.json()["records"]]
    assert plain in geos


async def test_geo_discarded_without_consent(client, db):
    w = await create_employee(db, "No", "Consent")  # geo_consent=False por defecto
    h = _auth(create_access_token(w.id, "empleado", pin_temporary=False))

    r = await client.post(
        "/fichaje/event",
        json={"event_type": "check_in", "modalidad": "movil", "geo": "1.0,2.0"},
        headers=h,
    )
    assert r.status_code == 201
    assert await _stored_geo(db, w.id) is None


async def test_geo_discarded_when_not_movil(client, db):
    w = await create_employee(db, "Si", "Consent")
    await _set_consent(db, w.id, True)
    h = _auth(create_access_token(w.id, "empleado", pin_temporary=False))

    # Con consentimiento pero modalidad presencial: no se almacena (minimización).
    r = await client.post(
        "/fichaje/event",
        json={"event_type": "check_in", "modalidad": "presencial", "geo": "1.0,2.0"},
        headers=h,
    )
    assert r.status_code == 201
    assert await _stored_geo(db, w.id) is None
