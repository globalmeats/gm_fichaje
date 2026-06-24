#!/usr/bin/env python3
"""Verificación de residencia UE y cifrado en tránsito para deploy/CI (REQ-23).

Falla con exit code 1 si la región configurada no es de la UE o si la conexión a la base de
datos no fuerza TLS. Pensado para correr ANTES de cada despliegue: no se debe desplegar datos
personales fuera de la UE ni transmitirlos sin cifrar.
"""

from __future__ import annotations

import sys

from app.core.config import RegionNotEUError, assert_eu_region, db_uses_tls, settings


def main() -> int:
    try:
        assert_eu_region()
    except RegionNotEUError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1
    if not db_uses_tls():
        print(
            "❌ La conexión a la base de datos no fuerza TLS (REQ-23). Añade sslmode=require "
            "a DATABASE_URL o desactiva db_require_tls solo en desarrollo.",
            file=sys.stderr,
        )
        return 1
    print(
        "✅ Región UE y TLS verificados "
        f"(deploy={settings.deploy_region}, supabase={settings.supabase_region})."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
