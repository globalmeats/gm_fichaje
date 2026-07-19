"""Dependencias compartidas de la API: sesión, trabajador autenticado y control de rol."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.db.session import get_session

_bearer = HTTPBearer(auto_error=True)


async def get_db() -> AsyncSession:  # pragma: no cover - thin wrapper
    async for s in get_session():
        yield s


def get_current_claims(
    creds: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict:
    """Decodifica el JWT y devuelve sus claims (worker_id, role, pin_temporary)."""
    try:
        return decode_token(creds.credentials)
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado.",
        ) from exc


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
