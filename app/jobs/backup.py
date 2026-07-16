"""Backup lógico cifrado a Cloudflare R2 con jurisdicción UE (REQ-03 / REQ-23).

El plan Free de Supabase no incluye backups gestionados (ver docs/DEFERRED.md): este job
es la red de seguridad de la conservación de 4 años. Exporta los DATOS de cada tabla
(`COPY ... TO STDOUT` en CSV vía asyncpg, en streaming); el ESQUEMA no se exporta porque
se reconstruye íntegro con las migraciones de `app/db/migrations/` (el manifest guarda
las versiones aplicadas para verificarlo en la restauración, ver `app/jobs/restore.py`).

El tar.gz se cifra con Fernet (`BACKUP_ENCRYPTION_KEY`, derivación idéntica a
`app/core/crypto.py`) ANTES de salir del proceso — a R2 solo llega ciphertext — y la
subida corre en un thread aparte (`asyncio.to_thread`) con timeouts y reintentos
adaptativos de botocore: el event loop nunca se bloquea y un fallo transitorio de red
no tumba el run.

Layout del bucket (se poda al final de cada run):

    daily/gm_fichaje_<UTC>.tar.gz.enc    -> últimos BACKUP_KEEP_DAILY (30)
    monthly/gm_fichaje_<UTC>.tar.gz.enc  -> copia del día 1 de mes; últimos 12

El run diario genera además actividad real en la BD: hace de keep-alive del proyecto
Supabase en plan Free (docs/DEFERRED.md).

Cron (Railway, servicio dedicado):

    python -m app.jobs.backup
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import io
import json
import tarfile
from datetime import datetime

import boto3
from boto3.s3.transfer import TransferConfig
from botocore.config import Config as BotoConfig
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings
from app.core.time import utc_now
from app.db.session import engine

ARCHIVE_PREFIX = "gm_fichaje"
MANIFEST_NAME = "manifest.json"

# schema_migrations no se exporta: el destino del restore se migra ANTES (mismo esquema)
# y el manifest conserva las versiones para verificar que backup y destino coinciden.
EXCLUDED_TABLES = frozenset({"schema_migrations"})


class BackupConfigError(RuntimeError):
    """Falta configuración del backup (clave de cifrado o credenciales R2)."""


class BackupIntegrityError(RuntimeError):
    """El objeto subido/descargado no coincide con lo esperado."""


# ---- Cifrado (mismo esquema de derivación que app/core/crypto.py) ----


def _fernet() -> Fernet:
    """Deriva la clave Fernet de `BACKUP_ENCRYPTION_KEY` (SHA-256 -> base64 url-safe)."""
    if not settings.backup_encryption_key:
        raise BackupConfigError("BACKUP_ENCRYPTION_KEY no configurada: el backup viaja cifrado.")
    digest = hashlib.sha256(settings.backup_encryption_key.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt(blob: bytes) -> bytes:
    return _fernet().encrypt(blob)


def decrypt(blob: bytes) -> bytes:
    try:
        return _fernet().decrypt(blob)
    except InvalidToken as exc:
        raise BackupIntegrityError(
            "No se pudo descifrar el backup: clave incorrecta o fichero corrupto."
        ) from exc


def require_r2_config() -> None:
    """Valida credenciales R2 y que el endpoint sea el jurisdiccional UE (REQ-23)."""
    missing = [
        name.upper()
        for name in ("r2_endpoint", "r2_access_key_id", "r2_secret_access_key", "r2_bucket")
        if not getattr(settings, name)
    ]
    if missing:
        raise BackupConfigError(f"Faltan variables de R2: {', '.join(missing)}.")
    if ".eu.r2.cloudflarestorage.com" not in settings.r2_endpoint:
        raise BackupConfigError(
            "R2_ENDPOINT no es el endpoint de jurisdicción UE "
            "(https://<account>.eu.r2.cloudflarestorage.com). Los backups contienen datos "
            "personales y deben residir en la UE (REQ-23)."
        )


# ---- Export (DB -> tar.gz en memoria) ----


def _toposort(tables: list[str], edges: list[tuple[str, str]]) -> list[str]:
    """Orden de restauración: padres (referenciados por FK) antes que hijos (Kahn)."""
    pending = {t: {p for c, p in edges if c == t and p != t and p in tables} for t in tables}
    ordered: list[str] = []
    while pending:
        ready = sorted(t for t, deps in pending.items() if not deps)
        if not ready:  # ciclo de FKs: orden alfabético como mejor esfuerzo
            ordered.extend(sorted(pending))
            break
        for t in ready:
            ordered.append(t)
            del pending[t]
        for deps in pending.values():
            deps.difference_update(ready)
    return ordered


async def export_archive() -> tuple[bytes, dict]:
    """Exporta los datos de todas las tablas y devuelve (tar.gz, manifest)."""
    tables_data: dict[str, bytes] = {}
    manifest_tables: dict[str, dict] = {}
    async with engine.connect() as conn:
        raw = await conn.get_raw_connection()
        driver = raw.driver_connection  # asyncpg.Connection (COPY nativo, streaming)
        tables = [
            r[0]
            for r in await driver.fetch(
                "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
            )
            if r[0] not in EXCLUDED_TABLES
        ]
        fks = [
            (r["child"], r["parent"])
            for r in await driver.fetch(
                "SELECT conrelid::regclass::text AS child, confrelid::regclass::text AS parent "
                "FROM pg_constraint "
                "WHERE contype='f' AND connamespace='public'::regnamespace"
            )
        ]
        versions = [
            r[0]
            for r in await driver.fetch("SELECT version FROM schema_migrations ORDER BY version")
        ]
        for table in tables:
            columns = [
                r[0]
                for r in await driver.fetch(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema='public' AND table_name=$1 ORDER BY ordinal_position",
                    table,
                )
            ]
            buf = io.BytesIO()
            await driver.copy_from_table(
                table, output=buf, columns=columns, format="csv", header=True
            )
            data = buf.getvalue()
            rows = await driver.fetchval(f'SELECT count(*) FROM "{table}"')
            tables_data[table] = data
            manifest_tables[table] = {
                "rows": rows,
                "columns": columns,
                "sha256": hashlib.sha256(data).hexdigest(),
            }

    manifest = {
        "created_at": utc_now().isoformat(),
        "application": ARCHIVE_PREFIX,
        "migrations": versions,
        "restore_order": _toposort(list(tables_data), fks),
        "tables": manifest_tables,
    }

    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode="w:gz") as tar:
        manifest_bytes = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
        for name, data in [(MANIFEST_NAME, manifest_bytes)] + [
            (f"{t}.csv", d) for t, d in tables_data.items()
        ]:
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return out.getvalue(), manifest


# ---- R2 (boto3 es síncrono: siempre se invoca vía asyncio.to_thread) ----


def s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.r2_endpoint,
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        region_name="auto",
        config=BotoConfig(
            connect_timeout=15,
            read_timeout=120,
            retries={"max_attempts": 8, "mode": "adaptive"},
            # R2 no soporta los checksums flexibles que boto3 calcula por defecto desde 1.36.
            request_checksum_calculation="when_required",
            response_checksum_validation="when_required",
        ),
    )


def _upload_and_verify(blob: bytes, key: str) -> None:
    """Sube el ciphertext y verifica el tamaño remoto (head) antes de dar el run por bueno."""
    s3 = s3_client()
    s3.upload_fileobj(
        io.BytesIO(blob),
        settings.r2_bucket,
        key,
        Config=TransferConfig(multipart_threshold=64 * 1024 * 1024, max_concurrency=4),
    )
    head = s3.head_object(Bucket=settings.r2_bucket, Key=key)
    if head["ContentLength"] != len(blob):
        raise BackupIntegrityError(
            f"Tamaño remoto ({head['ContentLength']}) != local ({len(blob)}) para {key}."
        )


def _copy_object(src_key: str, dst_key: str) -> None:
    s3_client().copy_object(
        CopySource={"Bucket": settings.r2_bucket, "Key": src_key},
        Bucket=settings.r2_bucket,
        Key=dst_key,
    )


def _download(key: str) -> bytes:
    buf = io.BytesIO()
    s3_client().download_fileobj(settings.r2_bucket, key, buf)
    return buf.getvalue()


def _prune(prefix: str, keep: int) -> list[str]:
    """Borra los objetos más antiguos de `prefix` dejando los `keep` últimos.

    El timestamp UTC va en el nombre, así que el orden lexicográfico es cronológico.
    """
    s3 = s3_client()
    keys: list[str] = []
    for page in s3.get_paginator("list_objects_v2").paginate(
        Bucket=settings.r2_bucket, Prefix=prefix
    ):
        keys.extend(obj["Key"] for obj in page.get("Contents", []))
    keys.sort()
    doomed = keys[:-keep] if keep > 0 and len(keys) > keep else []
    for i in range(0, len(doomed), 1000):
        s3.delete_objects(
            Bucket=settings.r2_bucket,
            Delete={"Objects": [{"Key": k} for k in doomed[i : i + 1000]]},
        )
    return doomed


# ---- Run ----


async def run_backup(*, now: datetime | None = None) -> dict:
    """Exporta, cifra, sube (daily + monthly si es día 1) y poda. Devuelve el resumen."""
    require_r2_config()
    now = now or utc_now()
    blob, manifest = await export_archive()
    ciphertext = encrypt(blob)

    name = f"{ARCHIVE_PREFIX}_{now.strftime('%Y%m%dT%H%M%SZ')}.tar.gz.enc"
    daily_key = f"daily/{name}"
    await asyncio.to_thread(_upload_and_verify, ciphertext, daily_key)

    monthly_key = None
    if now.day == 1:
        monthly_key = f"monthly/{name}"
        await asyncio.to_thread(_copy_object, daily_key, monthly_key)

    pruned = await asyncio.to_thread(_prune, "daily/", settings.backup_keep_daily)
    pruned += await asyncio.to_thread(_prune, "monthly/", settings.backup_keep_monthly)

    return {
        "key": daily_key,
        "monthly_key": monthly_key,
        "bytes": len(ciphertext),
        "rows": {t: m["rows"] for t, m in manifest["tables"].items()},
        "pruned": pruned,
    }


async def _main() -> None:
    result = await run_backup()
    total_rows = sum(result["rows"].values())
    print(
        f"✅ Backup subido a r2://{settings.r2_bucket}/{result['key']} "
        f"({result['bytes']} bytes cifrados, {total_rows} filas en "
        f"{len(result['rows'])} tablas)."
    )
    if result["monthly_key"]:
        print(f"   Copia mensual: {result['monthly_key']}")
    if result["pruned"]:
        print(f"   Retención aplicada: {len(result['pruned'])} backup(s) antiguos eliminados.")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(_main())
