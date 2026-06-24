"""Servicio de escritura sellada de `time_record` (REQ-02, REQ-15).

REGLA DE ORO (skill audit-trail): ningún endpoint inserta en `time_record` sin pasar por
`append_event`. Aquí se calcula SIEMPRE el sellado (hora del servidor en UTC + hash
encadenado por trabajador), de forma serializada para evitar carreras en `prev_hash`.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import chain_hash, iso8601, utc_now
from app.db.models import TimeRecord

# Semilla fija de la cadena: prev_hash del primer registro de cada trabajador.
GENESIS = "GENESIS"


def compute_record_hash(
    prev_hash: str,
    worker_id: uuid.UUID | str,
    occurred_at: datetime,
    event_type: str,
    modalidad: str,
    source: str,
    puesta_a_disposicion: bool,
) -> str:
    """Hash encadenado del registro: sha256(prev_hash || payload canónico).

    El payload incluye los campos sellables en un orden fijo; cualquier alteración
    posterior rompe este hash y, en cascada, el de todos los registros siguientes.
    """
    payload = (
        f"{worker_id}|{iso8601(occurred_at)}|{event_type}|"
        f"{modalidad}|{source}|{int(puesta_a_disposicion)}"
    )
    return chain_hash(prev_hash, payload)


async def append_event(
    db: AsyncSession,
    worker_id: uuid.UUID,
    event_type: str,
    *,
    modalidad: str = "presencial",
    source: str = "web",
    puesta_a_disposicion: bool = False,
) -> TimeRecord:
    """Inserta un evento sellado y encadenado para `worker_id` y hace commit.

    Serializa la cadena por trabajador con un advisory lock de transacción para que dos
    inserciones concurrentes no lean el mismo `prev_hash`.
    """
    # 1) Serializa por trabajador hasta el fin de la transacción (commit/rollback).
    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": str(worker_id)}
    )

    # 2) Último eslabón del trabajador -> prev_hash / seq.
    last = (
        await db.execute(
            select(TimeRecord.seq, TimeRecord.hash)
            .where(TimeRecord.worker_id == worker_id)
            .order_by(TimeRecord.seq.desc())
            .limit(1)
        )
    ).first()
    if last is None:
        prev_hash, seq = GENESIS, 1
    else:
        prev_hash, seq = last.hash, last.seq + 1

    # 3) Sella con la hora del servidor y calcula el hash.
    occurred_at = utc_now()
    record_hash = compute_record_hash(
        prev_hash, worker_id, occurred_at, event_type, modalidad, source, puesta_a_disposicion
    )

    record = TimeRecord(
        worker_id=worker_id,
        seq=seq,
        event_type=event_type,
        occurred_at=occurred_at,
        modalidad=modalidad,
        source=source,
        puesta_a_disposicion=puesta_a_disposicion,
        prev_hash=prev_hash,
        hash=record_hash,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def verify_chain(db: AsyncSession, worker_id: uuid.UUID) -> tuple[bool, int | None]:
    """Recomputa la cadena del trabajador en orden de `seq`.

    Devuelve `(True, None)` si es íntegra, o `(False, seq)` con el primer eslabón roto
    (hash recomputado distinto, o `prev_hash` que no concuerda con el anterior). Base del
    verificador periódico de Fase 4.
    """
    records = (
        await db.execute(
            select(TimeRecord)
            .where(TimeRecord.worker_id == worker_id)
            .order_by(TimeRecord.seq.asc())
        )
    ).scalars().all()

    prev_hash = GENESIS
    for record in records:
        if record.prev_hash != prev_hash:
            return False, record.seq
        expected = compute_record_hash(
            prev_hash,
            record.worker_id,
            record.occurred_at,
            record.event_type,
            record.modalidad,
            record.source,
            record.puesta_a_disposicion,
        )
        if record.hash != expected:
            return False, record.seq
        prev_hash = record.hash
    return True, None
