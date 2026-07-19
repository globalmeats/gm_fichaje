"""Simulacro backup -> restore (REQ-03, plan Free sin backups gestionados).

Corre contra el Postgres LOCAL de tests (regla del proyecto: pytest nunca contra prod).
Verifica el ciclo completo: export CSV por tabla, cifrado Fernet, restauración sobre BD
vaciada, integridad de la cadena de hashes tras restaurar, y las guardas (clave errónea,
destino con datos, esquema divergente).
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from app.audit.chain import append_event, verify_chain
from app.core.config import settings
from app.db.session import admin_engine
from app.jobs import backup, restore
from app.services.onboarding import create_employee


@pytest.fixture(autouse=True)
def _backup_key(monkeypatch):
    monkeypatch.setattr(settings, "backup_encryption_key", "clave-de-test-backup")


async def _seed(db):
    created = await create_employee(db, "Bak", "Upé")
    worker_id = uuid.UUID(created.id)
    r1 = await append_event(db, worker_id, "check_in")
    r2 = await append_event(db, worker_id, "check_out")
    hashes = [r1.hash, r2.hash]
    # Cierra la transacción ociosa del refresh post-commit: sus locks de lectura
    # bloquearían el TRUNCATE del restore (ver pg_stat_activity: idle in transaction).
    await db.rollback()
    return worker_id, hashes


async def test_roundtrip_backup_restore(db):
    worker_id, hashes = await _seed(db)

    blob, manifest = await backup.export_archive()
    assert manifest["tables"]["worker"]["rows"] == 1
    assert manifest["tables"]["time_record"]["rows"] == 2
    # El esquema no viaja en datos: viaja como versiones de migración verificables.
    assert "schema_migrations" not in manifest["tables"]
    assert manifest["migrations"]
    # Orden de restauración: worker (padre FK) antes que time_record.
    order = manifest["restore_order"]
    assert order.index("worker") < order.index("time_record")

    ciphertext = backup.encrypt(blob)
    assert ciphertext != blob
    assert backup.decrypt(ciphertext) == blob

    # Reset privilegiado (como el restore real): conexión admin, no la de app (app_rw).
    async with admin_engine.begin() as conn:
        # SEC-05: worker cascadea a time_record (guarda anti-TRUNCATE); desactiva triggers
        # solo en esta transacción de reset, igual que hace el restore.
        await conn.execute(text("SET LOCAL session_replication_role = 'replica'"))
        await conn.execute(text("TRUNCATE worker RESTART IDENTITY CASCADE"))

    restored = await restore.run_restore(ciphertext)
    assert restored["worker"] == 1
    assert restored["time_record"] == 2

    stored = (
        await db.execute(
            text("SELECT hash FROM time_record WHERE worker_id=:w ORDER BY seq"),
            {"w": worker_id},
        )
    ).scalars().all()
    assert stored == hashes
    ok, first_bad = await verify_chain(db, worker_id)
    assert ok, f"cadena rota tras el restore en seq={first_bad}"


async def test_decrypt_wrong_key_fails(db, monkeypatch):
    await _seed(db)
    blob, _ = await backup.export_archive()
    ciphertext = backup.encrypt(blob)
    monkeypatch.setattr(settings, "backup_encryption_key", "otra-clave")
    with pytest.raises(backup.BackupIntegrityError):
        restore.read_archive(ciphertext)


async def test_restore_rejects_non_empty_target(db):
    await _seed(db)
    blob, _ = await backup.export_archive()
    ciphertext = backup.encrypt(blob)
    # Sin vaciar el destino: debe negarse a pisar datos (salvo --force).
    with pytest.raises(restore.RestoreError, match="ya tiene"):
        await restore.run_restore(ciphertext)
    # Con force sí (simulacro local): trunca y restaura.
    restored = await restore.run_restore(ciphertext, force=True)
    assert restored["worker"] == 1


async def test_restore_rejects_schema_mismatch(db):
    await _seed(db)
    blob, _ = await backup.export_archive()
    manifest, tables = restore.read_archive(backup.encrypt(blob))
    manifest["migrations"].append("9999_futura")
    rebuilt = backup.encrypt(_rebuild_archive(manifest, tables))
    with pytest.raises(restore.RestoreError, match="migraciones"):
        await restore.run_restore(rebuilt, force=True)


def _rebuild_archive(manifest: dict, tables: dict[str, bytes]) -> bytes:
    import io
    import json
    import tarfile

    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode="w:gz") as tar:
        entries = [(backup.MANIFEST_NAME, json.dumps(manifest).encode())] + [
            (f"{t}.csv", d) for t, d in tables.items()
        ]
        for name, data in entries:
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return out.getvalue()


async def test_r2_config_guard(monkeypatch):
    monkeypatch.setattr(settings, "r2_endpoint", "https://acc.r2.cloudflarestorage.com")
    monkeypatch.setattr(settings, "r2_access_key_id", "x")
    monkeypatch.setattr(settings, "r2_secret_access_key", "x")
    monkeypatch.setattr(settings, "r2_bucket", "b")
    # Endpoint sin jurisdicción UE: se rechaza (REQ-23).
    with pytest.raises(backup.BackupConfigError, match="UE"):
        backup.require_r2_config()
    monkeypatch.setattr(
        settings, "r2_endpoint", "https://acc.eu.r2.cloudflarestorage.com"
    )
    backup.require_r2_config()
