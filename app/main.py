"""Punto de entrada FastAPI.

En el arranque verifica la residencia de datos en la UE (REQ-23): si la región no es
UE, la app NO levanta. Monta los routers de auth, admin, fichaje, reports, corrections,
export y portal (API JSON) y el router web SSR (Fase 7) con sus estáticos vendorizados.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api import absences, admin, auth, corrections, export, fichaje, portal, reports
from app.api.export import OVERSIGHT_ROLES
from app.core.config import assert_eu_region, assert_secure_secrets
from app.core.logging import setup_logging
from app.web import STATIC_DIR, templates
from app.web import router as web
from app.web.session import WebForbidden, WebRedirect, web_claims


@asynccontextmanager
async def lifespan(app: FastAPI):
    # REQ-23: no servir datos personales fuera de la UE.
    assert_eu_region()
    # B1: no arrancar en prod/staging con secretos por defecto de desarrollo.
    assert_secure_secrets()
    # R3: eventos de seguridad como JSON a stdout (los captura Railway).
    setup_logging()
    yield


app = FastAPI(title="Fichajes Global Meats", version="0.1.0", lifespan=lifespan)

# SEC-07: cabeceras de seguridad en toda respuesta. CSP permite Alpine ('unsafe-eval', usa
# Function()) y el <style> inline del layout ('unsafe-inline' en style-src); no hay bloques
# <script> inline. frame-ancestors 'none' bloquea el clickjacking sobre /login y /fichar.
_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-eval'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
)
_SECURITY_HEADERS = {
    "Content-Security-Policy": _CSP,
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
}


@app.middleware("http")
async def _security_headers(request: Request, call_next):
    response = await call_next(request)
    for name, value in _SECURITY_HEADERS.items():
        response.headers.setdefault(name, value)
    return response


app.include_router(auth.router)
app.include_router(absences.router)
app.include_router(admin.router)
app.include_router(fichaje.router)
app.include_router(reports.router)
app.include_router(corrections.router)
app.include_router(export.router)
app.include_router(portal.router)

# Frontend SSR (Fase 7): estáticos vendorizados + páginas HTML.
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.include_router(web.router)


@app.exception_handler(WebRedirect)
async def _web_redirect_handler(request: Request, exc: WebRedirect) -> RedirectResponse:
    # Sesión ausente/caducada o PIN temporal: la web redirige (no devuelve 401 JSON).
    return RedirectResponse(exc.location, status_code=exc.status_code)


@app.exception_handler(WebForbidden)
async def _web_forbidden_handler(request: Request, exc: WebForbidden):
    # Rol insuficiente: muestra el 403 (la barrera real la imponen API + RLS).
    return templates.TemplateResponse(
        request,
        "403.html",
        {"claims": web_claims(request), "oversight_roles": OVERSIGHT_ROLES},
        status_code=403,
    )


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
