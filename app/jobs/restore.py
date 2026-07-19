"""Restauración de un backup cifrado de app/jobs/backup.py (plan de recuperación REQ-03).

Restaura DATOS sobre una base de datos RECIÉN MIGRADA cuyo `schema_migrations` coincide
exactamente con el del backup (el manifest lo verifica; si difieren, aborta). Verifica el
SHA-256 de cada tabla antes de escribir nada. El destino debe estar vacío: con `--force`
se truncan antes las tablas de datos (pensado para simulacros en el Postgres LOCAL de
desarrollo — los simulacros NUNCA contra producción).

`time_policy` es un singleton sembrado por la migración: se sustituye siempre por la fila
del backup. Tras el COPY se recolocan las secuencias (serial/identity) al máximo presente.

Uso:
    python -m app.jobs.restore <ruta/al/backup.tar.gz.enc> [--force]
    python -m app.jobs.restore r2:daily/gm_fichaje_20260716T030000Z.tar.gz.enc [--force]
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import json
import sys
import tarfile
from pathlib import Path

from sqlalchemy import text

from app.db.session import engine
from app.jobs.backup import MANIFEST_NAME, _download, decrypt, require_r2_config

# El singleton de configuración se sustituye (la migración siembra su fila por defecto).
REPLACED_TABLES = frozenset({"time_policy"})


class RestoreError(RuntimeError):
    """El backup no es aplicable a este destino (esquema, integridad o datos previos)."""


def read_archive(blob: bytes) -> tuple[dict, dict[str, bytes]]:
    """Descifra y desempaqueta: devuelve (manifest, {tabla: csv}). Verifica SHA-256."""
    clear = decrypt(blob)
    tables: dict[str, bytes] = {}
    manifest: dict | None = None
    with tarfile.open(fileobj=io.BytesIO(clear), mode="r:gz") as tar:
        for member in tar.getmembers():
            data = tar.extractfile(member).read()  # type: ignore[union-attr]
            if member.name == MANIFEST_NAME:
                manifest = json.loads(data)
            else:
                tables[member.name.removesuffix(".csv")] = data
    if manifest is None:
        raise RestoreError(f"El archivo no contiene {MANIFEST_NAME}.")
    for name, meta in manifest["tables"].items():
        digest = hashlib.sha256(tables.get(name, b"")).hexdigest()
        if digest != meta["sha256"]:
            raise RestoreError(f"SHA-256 de '{name}' no coincide: backup corrupto.")
    return manifest, tables


async def run_restore(blob: bytes, *, force: bool = False) -> dict:
    """Aplica el backup en una única transacción. Devuelve filas restauradas por tabla."""
    manifest, tables = read_archive(blob)

    async with engine.begin() as conn:
        # SEC-05: desactiva los triggers (incluido el anti-TRUNCATE de 0014) durante la
        # reconstrucción. Solo afecta a esta transacción; el restore es una operación admin
        # deliberada sobre una BD recién migrada (simulacros en local, nunca contra prod).
        # Vía la conexión de SQLAlchemy para que aplique a la transacción que comparte el driver.
        await conn.execute(text("SET LOCAL session_replication_role = 'replica'"))
        raw = await conn.get_raw_connection()
        driver = raw.driver_connection

        versions = {
            r[0]
            for r in await driver.fetch("SELECT version FROM schema_migrations")
        }
        if versions != set(manifest["migrations"]):
            raise RestoreError(
                "Las migraciones del destino no coinciden con las del backup. "
                f"Backup: {sorted(manifest['migrations'])[-1]} | "
                f"destino: {sorted(versions)[-1] if versions else 'ninguna'}. "
                "Migra el destino al mismo punto antes de restaurar."
            )

        order: list[str] = manifest["restore_order"]
        for table in order:
            existing = await driver.fetchval(f'SELECT count(*) FROM "{table}"')
            if not existing:
                continue
            if table in REPLACED_TABLES:
                await driver.execute(f'DELETE FROM "{table}"')
            elif force:
                await driver.execute(f'TRUNCATE "{table}" CASCADE')
            else:
                raise RestoreError(
                    f"La tabla '{table}' ya tiene {existing} fila(s). Restaura sobre una BD "
                    "recién migrada, o usa --force (solo simulacros en local) para truncar."
                )

        restored: dict[str, int] = {}
        for table in order:
            meta = manifest["tables"][table]
            await driver.copy_to_table(
                table,
                source=io.BytesIO(tables[table]),
                columns=meta["columns"],
                format="csv",
                header=True,
            )
            restored[table] = meta["rows"]

        # Recoloca secuencias serial/identity al máximo restaurado.
        seq_cols = await driver.fetch(
            "SELECT table_name, column_name FROM information_schema.columns "
            "WHERE table_schema='public' "
            "AND (column_default LIKE 'nextval(%' OR is_identity='YES')"
        )
        for row in seq_cols:
            table, column = row["table_name"], row["column_name"]
            if table not in restored:
                continue
            await driver.execute(
                f"SELECT setval(pg_get_serial_sequence('{table}', '{column}'), "
                f'COALESCE((SELECT max("{column}") FROM "{table}"), 0) + 1, false)'
            )

    return restored


def _load_blob(source: str) -> bytes:
    if source.startswith("r2:"):
        require_r2_config()
        return _download(source.removeprefix("r2:"))
    return Path(source).read_bytes()


async def _main(source: str, force: bool) -> None:
    blob = await asyncio.to_thread(_load_blob, source)
    restored = await run_restore(blob, force=force)
    total = sum(restored.values())
    print(f"✅ Restauradas {total} filas en {len(restored)} tablas desde {source}.")
    await engine.dispose()


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--force"]
    if len(args) != 1:
        print(
            "Uso: python -m app.jobs.restore <backup.tar.gz.enc | r2:clave> [--force]",
            file=sys.stderr,
        )
        raise SystemExit(2)
    asyncio.run(_main(args[0], force="--force" in sys.argv[1:]))
