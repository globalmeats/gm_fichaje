"""Logging estructurado de eventos de seguridad y operación (informe go-live, R3).

Una línea JSON por evento a stdout: Railway la captura sin infraestructura extra.
Complementa —no sustituye— el rastro en BD de REQ-25 (`audit_alert`): aquí viaja lo
operativo (evento, IP real, momento) y NUNCA contenido: ni PINes, ni nombres, ni geo,
ni datos exportados (minimización, art. 32 RGPD). El código de empleado y la IP ya son
datos personales: la retención efectiva es la de los logs de Railway (corta) y queda
documentada en el RAT.

Uso:
    from app.core.logging import client_ip, log_event
    log_event("login_failed", code=worker.code, ip=client_ip(request))
"""

from __future__ import annotations

import json
import logging
import sys

from fastapi import Request

from app.core.config import settings
from app.core.time import utc_now

# Propaga por defecto (los tests capturan vía caplog); setup_logging() lo aísla en prod.
_logger = logging.getLogger("gm.security")


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data: dict = {
            "ts": utc_now().isoformat(),
            "level": record.levelname.lower(),
            "event": record.getMessage(),
        }
        data.update(getattr(record, "fields", {}))
        return json.dumps(data, ensure_ascii=False)


def setup_logging() -> None:
    """Instala el handler JSON a stdout (lo llama el lifespan). Idempotente."""
    if any(isinstance(h.formatter, _JsonFormatter) for h in _logger.handlers):
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JsonFormatter())
    _logger.addHandler(handler)
    _logger.setLevel(logging.INFO)
    _logger.propagate = False  # con handler propio, evita duplicados en el root


def log_event(event: str, *, warning: bool = False, **fields) -> None:
    """Emite un evento de seguridad/operación. `fields` van tal cual al JSON."""
    _logger.log(
        logging.WARNING if warning else logging.INFO,
        event,
        extra={"fields": {k: v for k, v in fields.items() if v is not None}},
    )


def client_ip(request: Request | None) -> str | None:
    """IP real del cliente para los logs.

    Detrás de Cloudflare (Fase 3 del go-live) se activa TRUST_CF_CONNECTING_IP y manda
    la cabecera `CF-Connecting-IP`; la cabecera NO se confía por defecto porque sin el
    proxy delante sería falsificable. Sin ella, la IP de la conexión (uvicorn ya
    resuelve `X-Forwarded-For` del proxy de Railway con `--proxy-headers`).
    """
    if request is None:
        return None
    if settings.trust_cf_connecting_ip:
        cf = request.headers.get("cf-connecting-ip")
        if cf:
            return cf
    return request.client.host if request.client else None
