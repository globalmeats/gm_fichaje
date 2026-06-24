"""Reportes de horas (REQ-08, REQ-12): totalización de horas extra por periodo de cómputo.

Acceso propio + supervisión: por defecto el reporte es del trabajador del JWT. Los roles de
supervisión pueden consultar a cualquier trabajador vía `?worker_id=`; el resto, solo el suyo.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from datetime import date as date_cls

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_claims, get_db
from app.core.time import utc_now
from app.db.models import TimePolicy, TimeRecord
from app.domain.hours import classify_overtime
from app.schemas.report import OvertimeReport

router = APIRouter(prefix="/reports", tags=["reports"])

# Roles que pueden ver las horas de otro trabajador (supervisión / inspección).
OVERSIGHT_ROLES = {"supervisor", "admin", "rlt", "inspeccion"}


def _minutes(td: timedelta) -> int:
    return int(td.total_seconds() // 60)


@router.get("/overtime", response_model=OvertimeReport)
async def overtime(
    worker_id: uuid.UUID | None = None,
    date: date_cls | None = None,
    claims: dict = Depends(get_current_claims),
    db: AsyncSession = Depends(get_db),
) -> OvertimeReport:
    own = uuid.UUID(claims["worker_id"])
    target = worker_id or own
    if target != own and claims.get("role") not in OVERSIGHT_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No autorizado para ver las horas de otro trabajador.",
        )

    policy = await db.get(TimePolicy, 1)
    if policy is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Política no inicializada."
        )

    reference = (
        datetime(date.year, date.month, date.day, tzinfo=UTC) if date else utc_now()
    )

    records = (
        await db.execute(
            select(TimeRecord)
            .where(TimeRecord.worker_id == target)
            .order_by(TimeRecord.seq.asc())
        )
    ).scalars().all()

    out = classify_overtime(records, policy, reference)
    return OvertimeReport(
        worker_id=target,
        period=out["period"],
        start=out["start"],
        end=out["end"],
        efectivo_min=_minutes(out["efectivo"]),
        ordinarias_min=_minutes(out["ordinarias"]),
        extra_min=_minutes(out["extra"]),
        ordinary_min=_minutes(out["ordinary"]),
    )
