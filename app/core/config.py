"""Configuración de la aplicación y verificación de residencia de datos en la UE.

REQ-23 (🟡): los datos personales deben residir en servidores de la UE. El arranque
de la app y el script de deploy FALLAN si la región configurada no es de la UE.
REQ-10 (🟢): base jurídica del tratamiento = cumplimiento de obligación legal
(art. 6.1.c RGPD); aquí solo dejamos constancia de la minimización por configuración.
"""

from __future__ import annotations

import re

from pydantic_settings import BaseSettings, SettingsConfigDict

# Allowlist de regiones consideradas dentro de la UE / EEE.
# Cubre los nombres habituales de AWS (eu-*), GCP (europe-*) y descripciones libres.
_EU_REGION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^eu[-_]", re.IGNORECASE),          # eu-west-1, eu-central-1, eu_west...
    re.compile(r"^europe[-_]", re.IGNORECASE),      # europe-west1 (GCP)
    re.compile(r"frankfurt|ireland|paris|madrid|stockholm|milan|amsterdam|zurich",
               re.IGNORECASE),
)


def is_eu_region(region: str | None) -> bool:
    """True si `region` parece pertenecer a la UE/EEE."""
    if not region:
        return False
    return any(p.search(region) for p in _EU_REGION_PATTERNS)


class RegionNotEUError(RuntimeError):
    """Se lanza cuando la región configurada no es de la UE (REQ-23)."""


class InsecureDefaultSecretError(RuntimeError):
    """Se lanza cuando un secreto crítico conserva su valor por defecto en prod (B1)."""


class DatabaseTLSError(RuntimeError):
    """Se lanza cuando la conexión a la BD no fuerza TLS y se exige (SEC-12 / REQ-23)."""


# Valores por defecto SOLO para desarrollo. Son la única fuente de verdad: se usan como
# `default=` de los campos y como referencia para detectarlos en producción.
DEV_JWT_SECRET = "change-me-in-production"
DEV_GEO_KEY = "dev-only-geo-key-change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Entorno de ejecución: "local" = desarrollo (defaults permitidos); cualquier otro valor
    # (production/staging) activa la guarda de secretos (B1).
    app_env: str = "local"

    # Base de datos
    database_url: str = "postgresql+asyncpg://fichajes:localdev@localhost:5432/fichajes"

    # JWT
    jwt_secret: str = DEV_JWT_SECRET
    jwt_expires_min: int = 30
    jwt_algorithm: str = "HS256"

    # Seguridad de login (PIN corto -> lockout imprescindible)
    max_failed_attempts: int = 5
    lockout_minutes: int = 15

    # Residencia de datos (REQ-23)
    deploy_region: str = "eu-west-1"
    supabase_region: str = "eu-west-1"
    # Cifrado en reposo + transporte (REQ-20/23). En producción la conexión a Postgres usa
    # TLS (sslmode=require) y la clave de cifrado se inyecta por entorno (el default es solo dev).
    db_require_tls: bool = True
    geo_encryption_key: str = DEV_GEO_KEY
    # Clave dedicada para cifrar los justificantes (SEC-08). Si se deja vacía, se deriva del
    # secreto de geo con separación de dominio (siguen siendo claves distintas). En producción
    # conviene configurar una DOC_ENCRYPTION_KEY aleatoria propia.
    doc_encryption_key: str = ""

    # Confiar en la cabecera CF-Connecting-IP para la IP real de los logs. Solo debe
    # activarse cuando Cloudflare está delante (Fase 3 del go-live); sin proxy, la
    # cabecera sería falsificable por el cliente.
    trust_cf_connecting_ip: bool = False

    # Ventana de tolerancia para fichajes offline sincronizados a posteriori (REQ-22):
    # un evento offline conserva su hora real, pero se rechaza si es futuro o demasiado viejo.
    max_offline_age_hours: int = 72

    # Backup cifrado a Cloudflare R2 (plan Free de Supabase sin backups gestionados; ver
    # docs/DEFERRED.md y app/jobs/backup.py). Solo los necesita el servicio cron de backup;
    # el job valida su presencia al arrancar. El endpoint debe ser el jurisdiccional UE
    # (`https://<account>.eu.r2.cloudflarestorage.com`) para cumplir REQ-23.
    backup_encryption_key: str = ""
    r2_endpoint: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket: str = ""
    backup_keep_daily: int = 30
    backup_keep_monthly: int = 12


settings = Settings()


def db_uses_tls(s: Settings = settings) -> bool:
    """True si la URL de BD fuerza TLS (sslmode/ssl=require) o no se exige TLS (dev)."""
    if not s.db_require_tls:
        return True
    url = s.database_url.lower()
    return "sslmode=require" in url or "ssl=require" in url or "ssl=true" in url


def assert_eu_region(s: Settings = settings) -> None:
    """Verifica que tanto el deploy como Supabase están en la UE. Lanza si no (REQ-23)."""
    offenders = []
    if not is_eu_region(s.deploy_region):
        offenders.append(f"DEPLOY_REGION={s.deploy_region!r}")
    if not is_eu_region(s.supabase_region):
        offenders.append(f"SUPABASE_REGION={s.supabase_region!r}")
    if offenders:
        raise RegionNotEUError(
            "Residencia de datos fuera de la UE (REQ-23). Regiones no válidas: "
            + ", ".join(offenders)
            + ". Los datos personales deben permanecer en servidores de la UE."
        )


def assert_db_tls(s: Settings = settings) -> None:
    """Aborta el arranque si se exige TLS a la BD pero la URL no lo fuerza (SEC-12/REQ-23)."""
    if not db_uses_tls(s):
        raise DatabaseTLSError(
            "La conexión a la base de datos no fuerza TLS (REQ-23). Añade ssl=require a "
            "DATABASE_URL, o desactiva DB_REQUIRE_TLS solo en desarrollo."
        )


def assert_secure_secrets(s: Settings = settings) -> None:
    """Aborta el arranque si un secreto crítico sigue con su default de dev en prod (B1).

    En `app_env == "local"` se permite arrancar con los defaults (desarrollo). En cualquier
    otro entorno, un `jwt_secret` por defecto haría falsificables los tokens y una
    `geo_encryption_key` por defecto dejaría la geo cifrada con una clave conocida.
    """
    if s.app_env == "local":
        return
    offenders = []
    if s.jwt_secret == DEV_JWT_SECRET:
        offenders.append("JWT_SECRET")
    if s.geo_encryption_key == DEV_GEO_KEY:
        offenders.append("GEO_ENCRYPTION_KEY")
    if offenders:
        raise InsecureDefaultSecretError(
            f"Arranque abortado (APP_ENV={s.app_env!r}): estas variables conservan su "
            "valor por defecto de desarrollo y deben configurarse con un secreto real: "
            + ", ".join(offenders)
            + "."
        )
