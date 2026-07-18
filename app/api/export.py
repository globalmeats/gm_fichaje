"""Exportación verificable de la jornada en PDF/CSV (REQ-04 vigente, REQ-17/19 reforma).

Disponibilidad inmediata on-demand: el informe siempre está accesible. Acceso self + oversight
(`OVERSIGHT_ROLES`): el trabajador descarga SOLO lo suyo; inspección/RLT/admin, de cualquier
trabajador y de solo lectura (acceso remoto de Inspección, REQ-17; control por rol, REQ-24).
El informe incluye identificación, detalle diario, correcciones y totales (REQ-19).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from datetime import date as date_cls

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_claims, get_db
from app.core.logging import log_event
from app.core.time import utc_now
from app.db.models import (
    Absence,
    AbsenceDocument,
    RecordCorrection,
    TimePolicy,
    TimeRecord,
    Worker,
)
from app.domain.absences import absence_hours, vacation_balance, vacation_days_taken
from app.domain.export import build_report, to_csv, to_pdf
from app.domain.hours import (
    annual_status,
    classify_overtime,
    period_window,
    reconstruct_journeys,
)
from app.domain.schedule import effective_vacation_days
from app.schemas.export import ExportAbsenceRow, ExportReport

router = APIRouter(prefix="/export", tags=["export"])

OVERSIGHT_ROLES = {"supervisor", "admin", "rlt", "inspeccion"}


async def load_report(
    db: AsyncSession,
    claims: dict,
    worker_id: uuid.UUID | None,
    start: date_cls | None,
    end: date_cls | None,
) -> ExportReport:
    """Resuelve acceso, carga registros + correcciones + totales y arma el informe."""
    own = uuid.UUID(claims["worker_id"])
    target = worker_id or own
    if target != own and claims.get("role") not in OVERSIGHT_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No autorizado para exportar los registros de otro trabajador.",
        )

    worker = await db.get(Worker, target)
    if worker is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trabajador no existe.")

    policy = await db.get(TimePolicy, 1)
    if policy is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Política no inicializada."
        )

    query = select(TimeRecord).where(TimeRecord.worker_id == target)
    if start is not None:
        query = query.where(
            TimeRecord.occurred_at >= datetime(start.year, start.month, start.day, tzinfo=UTC)
        )
    if end is not None:
        end_dt = datetime(end.year, end.month, end.day, tzinfo=UTC) + timedelta(days=1)
        query = query.where(TimeRecord.occurred_at < end_dt)
    records = (await db.execute(query.order_by(TimeRecord.seq.asc()))).scalars().all()

    corrections = (
        await db.execute(
            select(RecordCorrection)
            .where(RecordCorrection.worker_id == target)
            .order_by(RecordCorrection.seq.asc())
        )
    ).scalars().all()

    now = utc_now()
    summary = classify_overtime(
        records, policy, now, relation_type=worker.relation_type
    )

    # Tope anual del convenio (REQ-27) sobre horas efectivas del año natural.
    annual = annual_status(list(records), worker, policy, now)

    # Pausa total del periodo (descanso de comida visible), sobre la misma ventana del resumen.
    p_start, p_end = period_window(now, policy.computation_period)
    pausa_total = timedelta(0)
    for j in reconstruct_journeys(list(records)):
        if j.check_out is not None and p_start <= j.check_in < p_end:
            for ps, pe in j.pauses:
                pausa_total += pe - ps
    pausa_min = int(pausa_total.total_seconds() // 60)

    # Ausencias del trabajador: saldo de vacaciones del año + lista de ausencias del rango.
    all_absences = (
        await db.execute(select(Absence).where(Absence.worker_id == target))
    ).scalars().all()
    taken = vacation_days_taken(list(all_absences), now.year)
    entitled = effective_vacation_days(worker, policy)
    vacation = vacation_balance(entitled, taken)

    doc_ids = set(
        (
            await db.execute(
                select(AbsenceDocument.absence_id).where(
                    AbsenceDocument.absence_id.in_([a.id for a in all_absences])
                )
            )
        ).scalars().all()
    ) if all_absences else set()

    def _in_range(a: Absence) -> bool:
        if start is not None and a.end_date < start:
            return False
        if end is not None and a.start_date > end:
            return False
        return True

    absence_rows = [
        ExportAbsenceRow(
            absence_type=a.absence_type,
            subtype=a.subtype,
            start_date=a.start_date,
            end_date=a.end_date,
            start_time=a.start_time,
            end_time=a.end_time,
            status=a.status,
            justified=a.justified,
            hours=absence_hours(a),
            has_document=a.id in doc_ids,
        )
        for a in all_absences
        if _in_range(a)
    ]

    return build_report(
        worker,
        list(records),
        list(corrections),
        summary,
        annual=annual,
        vacation=vacation,
        absences=absence_rows,
        pausa_min=pausa_min,
        flexible_schedule=worker.flexible_schedule,
    )


@router.get("/records.csv")
async def export_csv(
    worker_id: uuid.UUID | None = None,
    start: date_cls | None = None,
    end: date_cls | None = None,
    claims: dict = Depends(get_current_claims),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    report = await load_report(db, claims, worker_id, start, end)
    content = to_csv(report)
    # R3: quién exporta qué rango (el contenido no se loguea).
    log_event(
        "export",
        format="csv",
        by=claims["worker_id"],
        target=report.employee_code,
        start=str(start) if start else None,
        end=str(end) if end else None,
    )
    filename = f"fichajes_{report.employee_code}.csv"
    return StreamingResponse(
        iter([content]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/records.pdf")
async def export_pdf(
    worker_id: uuid.UUID | None = None,
    start: date_cls | None = None,
    end: date_cls | None = None,
    claims: dict = Depends(get_current_claims),
    db: AsyncSession = Depends(get_db),
) -> Response:
    report = await load_report(db, claims, worker_id, start, end)
    content = to_pdf(report)
    log_event(
        "export",
        format="pdf",
        by=claims["worker_id"],
        target=report.employee_code,
        start=str(start) if start else None,
        end=str(end) if end else None,
    )
    filename = f"fichajes_{report.employee_code}.pdf"
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
