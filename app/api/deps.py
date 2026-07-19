"""Dependencias compartidas de la API: sesión, trabajador autenticado y control de rol."""

from __future__ import annotations

import json
import uuid
from collections.abc import Awaitable, Callable

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import decode_token
from app.db.models import Worker
from app.db.session import SessionLocal

_bearer = HTTPBearer(auto_error=True)

_INVALID_SESSION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED, detail="Sesión no válida o revocada."
)


async def set_request_claims(db: AsyncSession, claims: dict | None) -> None:
    """Fija (o limpia) los claims de la petición como GUC de sesión para la RLS (SEC-04a).

    Solo actúa si `rls_enforce` está activo. Se usa `set_config(..., is_local => false)` para
    que el valor SOBREVIVA a los commits que hace la app a mitad de request (p. ej.
    `append_event`); `get_db` lo limpia al abrir cada sesión, evitando fugas entre peticiones
    que reutilizan una conexión del pool. `auth.uid()`/`auth.jwt()` leen de este GUC.
    """
    if not settings.rls_enforce:
        return
    payload = "" if not claims else json.dumps(
        {"worker_id": str(claims.get("worker_id")), "role": claims.get("role")}
    )
    await db.execute(
        text("SELECT set_config('request.jwt.claims', :v, false)"), {"v": payload}
    )


async def get_db() -> AsyncSession:
    """Cede una sesión async y la cierra de forma determinista al terminar (BUG-09).

    Al abrir la sesión limpia los claims RLS (defensa contra fugas por reuso de conexión del
    pool); la petición autenticada los fija después vía `set_request_claims`.
    """
    async with SessionLocal() as s:
        await set_request_claims(s, None)
        yield s


async def get_current_claims(
    creds: HTTPAuthorizationCredentials = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Valida el JWT y lo contrasta con la BD en cada request (SEC-06/BUG-04).

    Además de decodificar, comprueba que el trabajador existe, sigue activo y que el claim
    `tv` coincide con su `token_version`: así un reset de PIN, un bloqueo, un cambio de rol
    o una desactivación invalidan de inmediato los tokens ya emitidos (logout servidor).
    """
    try:
        claims = decode_token(creds.credentials)
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado.",
        ) from exc
    try:
        worker_id = uuid.UUID(str(claims.get("worker_id")))
    except ValueError as exc:
        raise _INVALID_SESSION from exc
    worker = await db.get(Worker, worker_id)
    if worker is None or not worker.is_active or worker.token_version != claims.get("tv", 0):
        raise _INVALID_SESSION
    # El rol vigente manda sobre el del token (un cambio de rol ya invalidó el token, pero
    # por robustez servimos siempre el rol actual de la BD).
    claims["role"] = worker.role
    # RLS (SEC-04a): inyecta los claims validados para que las políticas gaten las queries
    # de datos del endpoint (persisten aunque el endpoint haga commit a mitad de request).
    await set_request_claims(db, claims)
    return claims


# Jerarquía de roles para operaciones sobre cuentas (SEC-01). Un actor solo puede actuar
# sobre cuentas de rango ESTRICTAMENTE inferior al suyo: así un supervisor no puede resetear
# el PIN de un admin (ni de otro supervisor) y apoderarse de la cuenta.
_ROLE_RANK: dict[str, int] = {
    "empleado": 0,
    "rlt": 0,
    "inspeccion": 0,
    "supervisor": 1,
    "admin": 2,
}


def role_rank(role: str | None) -> int:
    return _ROLE_RANK.get(role or "", 0)


def can_manage_account(actor_role: str | None, target_role: str | None) -> bool:
    """True si `actor_role` puede administrar (reset PIN, etc.) una cuenta de `target_role`."""
    return role_rank(actor_role) > role_rank(target_role)


def require_role(*roles: str) -> Callable[[dict], Awaitable[dict] | dict]:
    """Factory de dependencia que exige que el rol del JWT esté en `roles`."""

    def _checker(claims: dict = Depends(get_current_claims)) -> dict:
        if claims.get("role") not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Rol no autorizado para esta operación.",
            )
        return claims

    return _checker
