"""Endpoints de fichaje (REQ-01): registrar evento y consultar la jornada de hoy.

Aislamiento en capa de aplicación: cada trabajador solo opera y ve SUS registros, según
el `worker_id` del JWT (la app conecta como superusuario, así que la RLS no gatea hoy).
El sellado e inmutabilidad se delegan en `app/audit/chain.py` y el trigger de la BD.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_claims, get_db
from app.audit.chain import append_event
from app.core.time import utc_now
from app.db.models import TimeRecord
from app.domain.state_machine import InvalidTransition, next_state, reconstruct_state
from app.schemas.fichaje import (
    FichajeEventRequest,
    FichajeEventResponse,
    TodayEvent,
    TodayResponse,
)

router = APIRouter(prefix="/fichaje", tags=["fichaje"])


async def _ordered_event_types(db: AsyncSession, worker_id: uuid.UUID) -> list[str]:
    rows = (
        await db.execute(
            select(TimeRecord.event_type)
            .where(TimeRecord.worker_id == worker_id)
            .order_by(TimeRecord.seq.asc())
        )
    ).all()
    return [r.event_type for r in rows]


@router.post("/event", response_model=FichajeEventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(
    body: FichajeEventRequest,
    claims: dict = Depends(get_current_claims),
    db: AsyncSession = Depends(get_db),
) -> FichajeEventResponse:
    # Debe cambiar el PIN temporal antes de poder fichar.
    if claims.get("pin_temporary"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Debes cambiar tu PIN temporal antes de fichar.",
        )

    worker_id = uuid.UUID(claims["worker_id"])

    # Reconstruye el estado actual del histórico y valida la transición (REQ-01).
    current = reconstruct_state(await _ordered_event_types(db, worker_id))
    try:
        next_state(current, body.event_type)
    except InvalidTransition as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    record = await append_event(
        db,
        worker_id,
        body.event_type,
        modalidad=body.modalidad,
        source=body.source,
    )
    return FichajeEventResponse(
        id=str(record.id),
        seq=record.seq,
        event_type=record.event_type,
        occurred_at=record.occurred_at,
        prev_hash=record.prev_hash,
        hash=record.hash,
    )


@router.get("/today", response_model=TodayResponse)
async def today(
    claims: dict = Depends(get_current_claims),
    db: AsyncSession = Depends(get_db),
) -> TodayResponse:
    worker_id = uuid.UUID(claims["worker_id"])

    state = reconstruct_state(await _ordered_event_types(db, worker_id))

    day_start = utc_now().replace(hour=0, minute=0, second=0, microsecond=0)
    rows = (
        await db.execute(
            select(TimeRecord)
            .where(TimeRecord.worker_id == worker_id, TimeRecord.occurred_at >= day_start)
            .order_by(TimeRecord.seq.asc())
        )
    ).scalars().all()

    return TodayResponse(
        state=state.value,
        events=[
            TodayEvent(seq=r.seq, event_type=r.event_type, occurred_at=r.occurred_at)
            for r in rows
        ],
    )
