"""Prueba que la RLS bloquea de verdad a nivel de BD (SEC-04a).

Solo tiene sentido con `rls_enforce=True` y la app conectada como rol NO superusuario; en el
modo por defecto (superusuario, RLS inerte) se OMITE. Es la evidencia de la "segunda muralla":
aunque la capa de aplicación fallara, la BD no deja leer filas de otro trabajador.

Cómo ejecutarlo (rol restringido local, ver docs/DEFERRED.md / scripts):
    DATABASE_URL=...superuser  APP_DATABASE_URL=...app_rw  RLS_ENFORCE=true  pytest -q \
        app/tests/test_rls_enforcement.py
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from app.api.deps import set_request_claims
from app.audit.chain import append_event
from app.core.config import settings
from app.db.session import SessionLocal
from app.services.onboarding import create_employee

pytestmark = pytest.mark.skipif(
    not settings.rls_enforce, reason="RLS solo se evalúa con rls_enforce=True y rol restringido"
)


async def _count_time_records(claims: dict | None) -> int:
    """Cuenta time_record visibles bajo `claims` en una sesión de app (rol restringido)."""
    async with SessionLocal() as s:
        await set_request_claims(s, claims)
        return (await s.execute(text("SELECT count(*) FROM time_record"))).scalar_one()


async def test_rls_bloquea_lectura_cruzada(db):
    a = await create_employee(db, "Ana", "Uno")
    b = await create_employee(db, "Ben", "Dos")
    await append_event(db, uuid.UUID(a.id), "check_in")
    await append_event(db, uuid.UUID(a.id), "check_out")
    # 'a' ve sus 2 registros; 'b' no ve ninguno de 'a'.
    assert await _count_time_records({"worker_id": a.id, "role": "empleado"}) == 2
    assert await _count_time_records({"worker_id": b.id, "role": "empleado"}) == 0
    # Sin claims (deny-by-default): nada.
    assert await _count_time_records(None) == 0
    # Supervisión ve todo.
    assert await _count_time_records({"worker_id": b.id, "role": "supervisor"}) == 2
