"""Excepciones de ámbito de la obligación de registro (REQ-11).

Unit: `requires_time_record` / `registration_obligor` para alta dirección y ETT/subcontrata.
BD: el admin crea trabajadores con `relation_type`, `usuaria_id` y `geo_consent`.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.core.security import create_access_token
from app.db.models import Worker
from app.domain.scope import registration_obligor, requires_time_record
from app.services.onboarding import create_employee


@dataclass
class _Worker:
    id: uuid.UUID
    relation_type: str
    usuaria_id: uuid.UUID | None = None


# ---- unit ----

def test_alta_direccion_excluded_from_record():
    w = _Worker(id=uuid.uuid4(), relation_type="alta_direccion")
    assert requires_time_record(w) is False


def test_ordinaria_requires_record():
    w = _Worker(id=uuid.uuid4(), relation_type="ordinaria")
    assert requires_time_record(w) is True
    assert registration_obligor(w) is None


def test_tiempo_parcial_requires_record():
    w = _Worker(id=uuid.uuid4(), relation_type="tiempo_parcial")
    assert requires_time_record(w) is True


def test_ett_obligor_is_usuaria():
    usuaria = uuid.uuid4()
    w = _Worker(id=uuid.uuid4(), relation_type="ett", usuaria_id=usuaria)
    assert requires_time_record(w) is True  # seguimos registrando
    assert registration_obligor(w) == usuaria


def test_subcontrata_obligor_is_usuaria():
    usuaria = uuid.uuid4()
    w = _Worker(id=uuid.uuid4(), relation_type="subcontrata", usuaria_id=usuaria)
    assert registration_obligor(w) == usuaria


# ---- BD: admin crea con ámbito ----

def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_admin_creates_worker_with_relation_type(client, db):
    admin = await create_employee(db, "Adm", "Scope", role="admin")
    h = _auth(create_access_token(admin.id, "admin", pin_temporary=False))
    usuaria = str(uuid.uuid4())

    r = await client.post(
        "/admin/workers",
        json={
            "first_name": "Dir",
            "last_name": "Ectivo",
            "relation_type": "alta_direccion",
            "geo_consent": True,
            "usuaria_id": usuaria,
        },
        headers=h,
    )
    assert r.status_code == 201, r.text
    new_id = r.json()["id"]

    worker = await db.get(Worker, uuid.UUID(new_id))
    assert worker.relation_type == "alta_direccion"
    assert worker.geo_consent is True
    assert str(worker.usuaria_id) == usuaria
    # Excluido del registro obligatorio.
    assert requires_time_record(worker) is False


async def test_admin_rejects_invalid_relation_type(client, db):
    admin = await create_employee(db, "Adm", "Bad", role="admin")
    h = _auth(create_access_token(admin.id, "admin", pin_temporary=False))

    r = await client.post(
        "/admin/workers",
        json={"first_name": "X", "last_name": "Y", "relation_type": "inexistente"},
        headers=h,
    )
    assert r.status_code == 422
