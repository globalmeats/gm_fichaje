"""Inmutabilidad y verificación de cadena (REQ-02, REQ-15). Requiere BD.

El trigger `no_mutate_time_record` rechaza UPDATE/DELETE (incluso para el superusuario);
`verify_chain` confirma una cadena íntegra y detecta manipulación.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from app.audit.chain import append_event, verify_chain
from app.services.onboarding import create_employee


async def test_update_blocked_by_trigger(db):
    w = await create_employee(db, "Inmu", "Table")
    rec = await append_event(db, uuid.UUID(w.id), "check_in")

    with pytest.raises(Exception):  # noqa: B017 - el trigger lanza RAISE EXCEPTION
        await db.execute(
            text("UPDATE time_record SET event_type='check_out' WHERE id=:i"),
            {"i": str(rec.id)},
        )
    await db.rollback()


async def test_delete_blocked_by_trigger(db):
    w = await create_employee(db, "No", "Borrar")
    rec = await append_event(db, uuid.UUID(w.id), "check_in")

    with pytest.raises(Exception):  # noqa: B017 - el trigger lanza RAISE EXCEPTION
        await db.execute(text("DELETE FROM time_record WHERE id=:i"), {"i": str(rec.id)})
    await db.rollback()


async def test_verify_chain_ok(db):
    w = await create_employee(db, "Cad", "Ena")
    wid = uuid.UUID(w.id)
    await append_event(db, wid, "check_in")
    await append_event(db, wid, "check_out")

    ok, broken = await verify_chain(db, wid)
    assert ok is True
    assert broken is None


async def test_verify_chain_detects_tampering(db):
    w = await create_employee(db, "Man", "Ipula")
    wid = uuid.UUID(w.id)
    await append_event(db, wid, "check_in")
    await append_event(db, wid, "check_out")

    # Manipula un registro sorteando el trigger (solo posible deshabilitándolo: simula
    # un atacante con acceso directo a la BD). La cadena debe delatar el cambio.
    await db.execute(text("ALTER TABLE time_record DISABLE TRIGGER no_mutate_time_record"))
    await db.execute(
        text("UPDATE time_record SET event_type='break_start' WHERE worker_id=:w AND seq=1"),
        {"w": str(wid)},
    )
    await db.execute(text("ALTER TABLE time_record ENABLE TRIGGER no_mutate_time_record"))
    await db.commit()
    db.expire_all()

    ok, broken = await verify_chain(db, wid)
    assert ok is False
    assert broken == 1
