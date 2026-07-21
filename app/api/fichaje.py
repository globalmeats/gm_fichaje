"""Endpoints de fichaje (REQ-01): registrar evento y consultar la jornada de hoy.

Aislamiento en capa de aplicación: cada trabajador solo opera y ve SUS registros, según
el `worker_id` del JWT (la app conecta como superusuario, así que la RLS no gatea hoy).
El sellado e inmutabilidad se delegan en `app/audit/chain.py` y el trigger de la BD.
"""

from __future__ import annotations

import uuid
from datetime import UTC, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_claims, get_db
from app.audit.alerts import record_alert
from app.audit.chain import append_event
from app.core.config import settings
from app.core.crypto import encrypt_geo
from app.core.time import iso8601, madrid_today_start, utc_now
from app.db.models import (
    Absence,
    AuditAlert,
    RecordCorrection,
    TimePolicy,
    TimeRecord,
    Worker,
)
from app.domain.absences import vacation_balance, vacation_days_taken
from app.domain.corrections import apply_corrections
from app.domain.desconexion import is_off_hours
from app.domain.hours import (
    annual_status,
    annual_window,
    journey_effective,
    period_summary,
    reconstruct_journeys,
)
from app.domain.schedule import effective_vacation_days
from app.domain.state_machine import InvalidTransition, next_state, reconstruct_state
from app.schemas.fichaje import (
    AnnualSummary,
    FichajeEventRequest,
    FichajeEventResponse,
    JourneySummary,
    OfflineEventRequest,
    PeriodSummary,
    SummaryResponse,
    SyncEventResponse,
    TodayEvent,
    TodayResponse,
    VacationSummary,
)

router = APIRouter(prefix="/fichaje", tags=["fichaje"])


def _geo_to_store(worker: Worker | None, modalidad: str, geo: str | None) -> str | None:
    """Decide y cifra la geo a almacenar (REQ-20, minimización).

    Solo se guarda (cifrada) si hay consentimiento y la modalidad es móvil (es donde la
    ubicación aporta al control horario). En cualquier otro caso se descarta: nunca rastreo
    continuo, solo el instante del evento.
    """
    if geo and worker is not None and worker.geo_consent and modalidad == "movil":
        return encrypt_geo(geo)
    return None


async def _alert_if_off_hours(db: AsyncSession, worker_id: uuid.UUID, occurred_at) -> None:
    """Si el evento cae fuera de la ventana de desconexión, deja una alerta off_hours (REQ-26)."""
    policy = await db.get(TimePolicy, 1)
    if policy is not None and is_off_hours(occurred_at, policy):
        await record_alert(
            db,
            "off_hours",
            f"Fichaje fuera de la ventana de desconexión digital a las {iso8601(occurred_at)}.",
            worker_id=worker_id,
            severity="info",
        )


async def _alert_if_annual_cap(db: AsyncSession, worker: Worker | None) -> None:
    """Si el trabajador supera (o se acerca a) su tope anual, deja una alerta annual_cap (REQ-27).

    No bloquea el fichaje (misma filosofía que off_hours). Deduplica: no repite la alerta si ya
    hay una para ese trabajador dentro del año natural en curso.
    """
    if worker is None:
        return
    policy = await db.get(TimePolicy, 1)
    if policy is None:
        return
    now = utc_now()
    # BUG-05: solo el año natural en curso influye en el tope anual. Acotamos la consulta a
    # `occurred_at >= inicio del año` (frontera Madrid→UTC): las jornadas con check_in en el año
    # se capturan enteras y las que cruzan el 31-dic pertenecen al año anterior (no cuentan aquí),
    # así que `annual_status` da el mismo resultado que cargando todo el histórico.
    year_start, _ = annual_window(now)
    records = (
        await db.execute(
            select(TimeRecord)
            .where(TimeRecord.worker_id == worker.id, TimeRecord.occurred_at >= year_start)
            .order_by(TimeRecord.seq.asc())
        )
    ).scalars().all()
    corrections = (
        await db.execute(
            select(RecordCorrection).where(RecordCorrection.worker_id == worker.id)
        )
    ).scalars().all()
    status_ = annual_status(
        apply_corrections(list(records), list(corrections)), worker, policy, now
    )
    if not (status_["exceeded"] or status_["near"]):
        return

    # Deduplicación: ¿ya hay una alerta annual_cap de este trabajador este año?
    existing = (
        await db.execute(
            select(AuditAlert.id).where(
                AuditAlert.alert_type == "annual_cap",
                AuditAlert.worker_id == worker.id,
                AuditAlert.detected_at >= status_["start"],
            )
        )
    ).first()
    if existing is not None:
        return

    worked_h = status_["worked"].total_seconds() / 3600
    kind = "superado" if status_["exceeded"] else "cercano al"
    await record_alert(
        db,
        "annual_cap",
        f"Tope anual de jornada {kind} límite ({worked_h:.1f}h de "
        f"{status_['cap_hours']:.0f}h en {status_['year']}).",
        worker_id=worker.id,
        severity="warning",
    )


async def _ordered_event_types(db: AsyncSession, worker_id: uuid.UUID) -> list[str]:
    """Eventos (en orden de seq) de la jornada ABIERTA actual, para reconstruir el estado.

    Optimización (BUG-05): el estado solo depende de los eventos posteriores al último
    `check_out` (cada check_out devuelve a IDLE). Acotamos la consulta a `seq` > el del último
    check_out en vez de cargar todo el histórico; el estado reconstruido es idéntico.
    """
    last_checkout = (
        select(func.max(TimeRecord.seq))
        .where(TimeRecord.worker_id == worker_id, TimeRecord.event_type == "check_out")
        .scalar_subquery()
    )
    rows = (
        await db.execute(
            select(TimeRecord.event_type)
            .where(
                TimeRecord.worker_id == worker_id,
                TimeRecord.seq > func.coalesce(last_checkout, 0),
            )
            .order_by(TimeRecord.seq.asc())
        )
    ).all()
    return [r.event_type for r in rows]


def _state_validator(event_type: str):
    """Validador de transición para `append_event`: se ejecuta bajo el lock (REQ-01)."""

    def _validate(ordered_types: list[str]) -> None:
        next_state(reconstruct_state(ordered_types), event_type)

    return _validate


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

    # `travel_computes` solo es significativo en desplazamientos; el resto guarda el neutro.
    travel_computes = body.travel_computes if body.event_type.startswith("travel_") else True
    worker = await db.get(Worker, worker_id)
    stored_geo = _geo_to_store(worker, body.modalidad, body.geo)
    # La transición (REQ-01) se valida DENTRO del lock de append_event: check + act atómicos.
    try:
        record = await append_event(
            db,
            worker_id,
            body.event_type,
            modalidad=body.modalidad,
            source=body.source,
            travel_computes=travel_computes,
            geo=stored_geo,
            validate_transition=_state_validator(body.event_type),
        )
    except InvalidTransition as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    await _alert_if_off_hours(db, worker_id, record.occurred_at)
    await _alert_if_annual_cap(db, worker)
    return FichajeEventResponse(
        id=str(record.id),
        seq=record.seq,
        event_type=record.event_type,
        occurred_at=record.occurred_at,
        prev_hash=record.prev_hash,
        hash=record.hash,
    )


@router.post("/sync", response_model=SyncEventResponse, status_code=status.HTTP_201_CREATED)
async def sync_event(
    body: OfflineEventRequest,
    claims: dict = Depends(get_current_claims),
    db: AsyncSession = Depends(get_db),
) -> SyncEventResponse:
    """Sincroniza un fichaje capturado offline (REQ-22).

    Conserva la hora REAL del cliente (`occurred_at`) dentro de una ventana de tolerancia, y
    deduplica por `client_event_id`: reenviar el mismo evento de la cola de sincronización no
    crea un registro duplicado (idempotente). Excepción acotada a REQ-15 solo para offline.
    """
    if claims.get("pin_temporary"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Debes cambiar tu PIN temporal antes de fichar.",
        )

    worker_id = uuid.UUID(claims["worker_id"])

    # 1) Ventana de tolerancia (REQ-22): ni futuro ni demasiado viejo.
    occurred = body.occurred_at
    if occurred.tzinfo is None:
        occurred = occurred.replace(tzinfo=UTC)
    now = utc_now()
    earliest = now - timedelta(hours=settings.max_offline_age_hours)
    if occurred > now or occurred < earliest:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "occurred_at fuera de la ventana de tolerancia de sincronización "
                f"(máximo {settings.max_offline_age_hours}h y no futuro)."
            ),
        )

    # 2) Idempotencia (REQ-22): si ya se sincronizó este evento, devolverlo sin duplicar.
    existing = (
        await db.execute(
            select(TimeRecord).where(TimeRecord.client_event_id == body.client_event_id)
        )
    ).scalar_one_or_none()
    if existing is not None:
        return SyncEventResponse(
            id=str(existing.id),
            seq=existing.seq,
            event_type=existing.event_type,
            occurred_at=existing.occurred_at,
            prev_hash=existing.prev_hash,
            hash=existing.hash,
            deduplicated=True,
        )

    # 3) Valida la transición (bajo el lock de append_event) e inserta atómicamente.
    travel_computes = body.travel_computes if body.event_type.startswith("travel_") else True
    worker = await db.get(Worker, worker_id)
    stored_geo = _geo_to_store(worker, body.modalidad, body.geo)
    try:
        record = await append_event(
            db,
            worker_id,
            body.event_type,
            modalidad=body.modalidad,
            source="offline_sync",
            travel_computes=travel_computes,
            geo=stored_geo,
            client_event_id=body.client_event_id,
            occurred_at=occurred,
            validate_transition=_state_validator(body.event_type),
        )
    except InvalidTransition as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    await _alert_if_off_hours(db, worker_id, record.occurred_at)
    await _alert_if_annual_cap(db, worker)
    return SyncEventResponse(
        id=str(record.id),
        seq=record.seq,
        event_type=record.event_type,
        occurred_at=record.occurred_at,
        prev_hash=record.prev_hash,
        hash=record.hash,
        deduplicated=False,
    )


@router.get("/today", response_model=TodayResponse)
async def today(
    claims: dict = Depends(get_current_claims),
    db: AsyncSession = Depends(get_db),
) -> TodayResponse:
    worker_id = uuid.UUID(claims["worker_id"])

    # Lectura defensiva: nunca 500 aunque el histórico llegara a ser incoherente (BUG-01).
    state = reconstruct_state(await _ordered_event_types(db, worker_id), strict=False)

    day_start = madrid_today_start(utc_now())  # "hoy" = día local de Madrid (BUG-02)
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


def _minutes(td) -> int:
    return int(td.total_seconds() // 60)


@router.get("/summary", response_model=SummaryResponse)
async def summary(
    claims: dict = Depends(get_current_claims),
    db: AsyncSession = Depends(get_db),
) -> SummaryResponse:
    """Tiempo efectivo del propio trabajador: jornadas de hoy + total del periodo (REQ-07/09/12).

    Solo datos del `worker_id` del JWT (aislamiento en capa de aplicación).
    """
    worker_id = uuid.UUID(claims["worker_id"])
    policy = await db.get(TimePolicy, 1)

    records = (
        await db.execute(
            select(TimeRecord)
            .where(TimeRecord.worker_id == worker_id)
            .order_by(TimeRecord.seq.asc())
        )
    ).scalars().all()
    # REQ-16: computar sobre la vista efectiva (con correcciones aplicadas).
    corrections = (
        await db.execute(
            select(RecordCorrection)
            .where(RecordCorrection.worker_id == worker_id)
            .order_by(RecordCorrection.seq.asc())
        )
    ).scalars().all()
    effective = apply_corrections(list(records), list(corrections))

    now = utc_now()
    day_start = madrid_today_start(now)  # "hoy" = día local de Madrid (BUG-02)

    today_journeys: list[JourneySummary] = []
    for j in reconstruct_journeys(effective):
        if j.check_in < day_start:
            continue
        bruto = (j.check_out - j.check_in) if j.check_out else None
        pausa = sum((end - start for start, end in j.pauses), timedelta(0))
        travel_no = sum(
            (end - start for start, end, computes in j.travels if not computes),
            timedelta(0),
        )
        today_journeys.append(
            JourneySummary(
                check_in=j.check_in,
                check_out=j.check_out,
                bruto_min=_minutes(bruto) if bruto is not None else 0,
                pausa_computable_min=(
                    _minutes(pausa) if policy.pause_computable_default else 0
                ),
                travel_no_computa_min=_minutes(travel_no),
                efectivo_min=_minutes(journey_effective(j, policy)),
                open=j.open,
            )
        )

    period = period_summary(effective, policy, now)

    # Estado anual del tope de jornada (REQ-27) y saldo de vacaciones (REQ-18/28) propios.
    worker = await db.get(Worker, worker_id)
    annual = annual_status(effective, worker, policy, now)
    absences = (
        await db.execute(select(Absence).where(Absence.worker_id == worker_id))
    ).scalars().all()
    taken = vacation_days_taken(list(absences), now.year)
    bal = vacation_balance(effective_vacation_days(worker, policy), taken)

    return SummaryResponse(
        today=today_journeys,
        period=PeriodSummary(
            period=period["period"],
            start=period["start"],
            end=period["end"],
            efectivo_min=_minutes(period["efectivo"]),
        ),
        annual=AnnualSummary(
            year=annual["year"],
            worked_min=_minutes(annual["worked"]),
            cap_min=_minutes(annual["cap"]),
            remaining_min=_minutes(annual["remaining"]),
            exceeded=annual["exceeded"],
            near=annual["near"],
        ),
        vacation=VacationSummary(
            year=now.year,
            entitled=bal["entitled"],
            taken=bal["taken"],
            remaining=bal["remaining"],
        ),
    )
