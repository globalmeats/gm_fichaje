"""Fixtures de test.

Los tests que tocan BD usan el `DATABASE_URL` configurado (Postgres local vía
docker-compose en dev; servicio Postgres en CI). Si la BD no está disponible, esos
tests se omiten (`skip`) en lugar de fallar.
"""

from __future__ import annotations

import socket

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import InterfaceError, OperationalError

from app.db import migrate

# El fixture `db` usa la conexión ADMIN (privilegiada): los tests preparan e inspeccionan
# datos directamente, saltándose la RLS. La API (fixture `client`) usa la conexión de app,
# que con `rls_enforce` aplica la RLS. Con rls_enforce=False ambas coinciden (superusuario).
from app.db.session import AdminSessionLocal, admin_engine, engine
from app.main import app

# Solo estos errores (BD no disponible) justifican SKIP: en local sin Postgres los tests de
# integración se omiten. Un fallo de migración, de esquema o de SQL debe PROPAGARSE y poner CI
# en ROJO (TEST-01): capturarlo como skip enmascararía regresiones en un sistema de compliance.
_DB_UNAVAILABLE = (OperationalError, InterfaceError, ConnectionError, socket.gaierror, OSError)


@pytest_asyncio.fixture
async def prepared():
    """Aplica migraciones y deja la tabla worker vacía. Omite si no hay BD."""
    try:
        await migrate.run()
        async with admin_engine.begin() as conn:
            # El TRUNCATE de worker cascadea a time_record/record_correction, que desde 0014
            # tienen guarda anti-TRUNCATE (SEC-05). En el reset deliberado de test desactivamos
            # los triggers solo en esta transacción (como hace el restore).
            await conn.execute(text("SET LOCAL session_replication_role = 'replica'"))
            await conn.execute(text("TRUNCATE worker RESTART IDENTITY CASCADE"))
            # time_policy es un singleton de config (no se trunca): se reinicia a los
            # valores por defecto para que cada test parta de un estado conocido.
            await conn.execute(
                text(
                    "UPDATE time_policy SET pause_computable_default=true, "
                    "computation_period='monthly', ordinary_hours_per_period=160, "
                    "desconexion_start=NULL, desconexion_end=NULL, "
                    "annual_hours_cap=1760, annual_vacation_days=22 WHERE id=1"
                )
            )
    except _DB_UNAVAILABLE as exc:
        pytest.skip(f"Base de datos no disponible para tests de integración: {exc}")
    yield
    # Aísla del loop del siguiente test (asyncpg liga el pool al event loop). Con rls_enforce
    # el engine de app (app_rw) es distinto del admin: hay que disponer ambos.
    await admin_engine.dispose()
    if engine is not admin_engine:
        await engine.dispose()


@pytest_asyncio.fixture
async def db(prepared):
    async with AdminSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client(prepared):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
