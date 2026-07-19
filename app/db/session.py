"""Engines y sesiones async de SQLAlchemy 2.x (Supabase/Postgres vía asyncpg).

Dos roles de conexión (SEC-04a):

- **admin** (`admin_engine`/`AdminSessionLocal`): conexión PRIVILEGIADA. La usan migraciones,
  seed y jobs (retention/backup/restore). Bypassa RLS por diseño (tareas de sistema).
- **app** (`engine`/`SessionLocal`): la usan api y web. Si `rls_enforce` es True, apunta a
  `app_database_url` (rol NO superusuario) para que las políticas RLS se evalúen; si es False,
  coincide con la admin (comportamiento actual, RLS inerte).

La inyección de claims del JWT en la sesión de app vive en `app/api/deps.py` y
`app/web/session.py` (no aquí), porque depende de la petición autenticada.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

# Conexión privilegiada (migraciones, seed, jobs). Siempre database_url.
admin_engine = create_async_engine(settings.database_url, pool_pre_ping=True)
AdminSessionLocal = async_sessionmaker(
    admin_engine, class_=AsyncSession, expire_on_commit=False
)

# Conexión de la app (api/web). Con rls_enforce usa el rol restringido; si no, la misma admin.
_use_restricted = settings.rls_enforce and bool(settings.app_database_url)
_app_url = settings.app_database_url if _use_restricted else settings.database_url
engine = (
    admin_engine if _app_url == settings.database_url
    else create_async_engine(_app_url, pool_pre_ping=True)
)
SessionLocal = (
    AdminSessionLocal if engine is admin_engine
    else async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
)


async def get_session() -> AsyncIterator[AsyncSession]:
    """Dependencia FastAPI: cede una sesión async (rol de app) y la cierra al terminar."""
    async with SessionLocal() as session:
        yield session
