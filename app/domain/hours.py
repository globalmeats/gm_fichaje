"""Cálculo de tiempo efectivo (REQ-07, REQ-09, REQ-12). Lógica pura, sin BD.

Reconstruye jornadas del histórico append-only y calcula el tiempo EFECTIVO distinguiéndolo
del bruto, para evitar la presunción legal (ver skill fichaje-domain / calculo-horas):

    bruto       = check_out − check_in
    efectivo    = bruto − Σ pausas computables − Σ desplazamientos que NO computan

Polaridad de `travel_computes` (¡inversa del antiguo `puesta_a_disposicion`!):
    travel_computes = true  → ese desplazamiento SÍ computa → NO se resta.
    travel_computes = false → NO computa → SÍ se resta.

La computabilidad de las pausas se decide por política global (`is_pause_computable`),
costura para un override por-evento futuro sin tocar el sellado.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Protocol

from app.core.time import add_months, madrid_date, madrid_midnight_utc
from app.domain.schedule import effective_annual_cap

# Umbral de aviso del tope anual: a partir de este ratio de consumo se considera "cerca".
ANNUAL_WARNING_RATIO = 0.9


class _Record(Protocol):
    """Mínimo que necesita un `time_record` para reconstruir jornadas (duck typing)."""

    event_type: str
    occurred_at: datetime
    travel_computes: bool


class _Policy(Protocol):
    pause_computable_default: bool
    computation_period: str
    ordinary_hours_per_period: float


@dataclass
class Journey:
    """Una jornada: desde un check_in hasta su check_out (o abierta si falta)."""

    check_in: datetime
    check_out: datetime | None = None
    pauses: list[tuple[datetime, datetime]] = field(default_factory=list)
    # (inicio, fin, computes): computes=False → ese tramo se resta del efectivo.
    travels: list[tuple[datetime, datetime, bool]] = field(default_factory=list)

    @property
    def open(self) -> bool:
        return self.check_out is None


def reconstruct_journeys(records: list[_Record]) -> list[Journey]:
    """Pliega los `time_record` (en orden de `seq`) en jornadas.

    Empareja break_start/break_end y travel_start/travel_end dentro de la jornada abierta.
    Una jornada sin check_out queda `open` (incidencia: nunca se autocompleta — la
    inmutabilidad lo prohíbe). El flag `travel_computes` se toma del evento `travel_start`.
    """
    journeys: list[Journey] = []
    current: Journey | None = None
    pause_start: datetime | None = None
    travel_start: datetime | None = None
    travel_flag = True

    for r in records:
        if r.event_type == "check_in":
            current = Journey(check_in=r.occurred_at)
            journeys.append(current)
            pause_start = travel_start = None
        elif current is None:
            # Evento fuera de una jornada abierta: histórico imposible (lo evita la máquina
            # de estados en escritura). Se ignora defensivamente.
            continue
        elif r.event_type == "break_start":
            pause_start = r.occurred_at
        elif r.event_type == "break_end":
            if pause_start is not None:
                current.pauses.append((pause_start, r.occurred_at))
                pause_start = None
        elif r.event_type == "travel_start":
            travel_start = r.occurred_at
            travel_flag = r.travel_computes
        elif r.event_type == "travel_end":
            if travel_start is not None:
                current.travels.append((travel_start, r.occurred_at, travel_flag))
                travel_start = None
        elif r.event_type == "check_out":
            current.check_out = r.occurred_at
            current = None
            pause_start = travel_start = None

    return journeys


def is_pause_computable(policy: _Policy) -> bool:
    """¿Las pausas se descuentan del tiempo efectivo? Por ahora, política global.

    Costura para un override por-evento futuro (la doc lo modela por-pausa) sin rehacer el
    sellado de `time_record`.
    """
    return policy.pause_computable_default


def journey_coherent(journey: Journey) -> bool:
    """False si la jornada tiene una incoherencia temporal (p. ej. tras una corrección a medias):
    salida antes de entrada, o una pausa/desplazamiento que termina antes de empezar."""
    if journey.check_out is not None and journey.check_out < journey.check_in:
        return False
    if any(end < start for start, end in journey.pauses):
        return False
    if any(end < start for start, end, _ in journey.travels):
        return False
    return True


def journey_effective(journey: Journey, policy: _Policy) -> timedelta:
    """Tiempo efectivo de una jornada cerrada.

    Jornada abierta (sin check_out) → no computa (incidencia): devuelve 0.
    Jornada temporalmente INCOHERENTE (ver `journey_coherent`) → 0 hasta que se corrija: no se
    computan tiempos negativos/absurdos; la discrepancia se señala aparte (banner).
    """
    if journey.check_out is None or not journey_coherent(journey):
        return timedelta(0)

    effective = journey.check_out - journey.check_in
    if is_pause_computable(policy):
        for start, end in journey.pauses:
            effective -= end - start
    for start, end, computes in journey.travels:
        if not computes:
            effective -= end - start
    return effective


def period_window(now: datetime, period: str) -> tuple[datetime, datetime]:
    """Ventana [inicio, fin) del periodo de cómputo (REQ-12), en fronteras de Madrid → UTC."""
    d = madrid_date(now)
    if period == "daily":
        return madrid_midnight_utc(d), madrid_midnight_utc(d + timedelta(days=1))
    if period == "weekly":
        monday = d - timedelta(days=d.weekday())
        return madrid_midnight_utc(monday), madrid_midnight_utc(monday + timedelta(days=7))
    # monthly (default)
    first = d.replace(day=1)
    return madrid_midnight_utc(first), madrid_midnight_utc(add_months(first, 1))


def period_summary(records: list[_Record], policy: _Policy, now: datetime) -> dict:
    """Suma el tiempo efectivo de las jornadas cerradas dentro del periodo actual."""
    start, end = period_window(now, policy.computation_period)
    total = timedelta(0)
    for j in reconstruct_journeys(records):
        if j.check_out is not None and start <= j.check_in < end:
            total += journey_effective(j, policy)
    return {
        "efectivo": total,
        "period": policy.computation_period,
        "start": start,
        "end": end,
    }


def annual_window(now: datetime) -> tuple[datetime, datetime]:
    """Ventana [1 ene, 1 ene del año siguiente) para el cómputo anual (REQ-27), Madrid → UTC."""
    year = madrid_date(now).year
    return madrid_midnight_utc(date(year, 1, 1)), madrid_midnight_utc(date(year + 1, 1, 1))


def annual_worked(records: list[_Record], policy: _Policy, now: datetime) -> timedelta:
    """Suma el tiempo efectivo de las jornadas cerradas dentro del año natural en curso."""
    start, end = annual_window(now)
    total = timedelta(0)
    for j in reconstruct_journeys(records):
        if j.check_out is not None and start <= j.check_in < end:
            total += journey_effective(j, policy)
    return total


def annual_status(records: list[_Record], worker, policy: _Policy, now: datetime) -> dict:
    """Estado del tope anual del trabajador (REQ-27): trabajado, tope, restante y flags.

    `cap` es el tope efectivo del trabajador (su `annual_hours_cap` o el default global del
    convenio). `exceeded` marca que se ha superado el tope; `near` que se ha alcanzado el
    umbral de aviso (`ANNUAL_WARNING_RATIO`). El cómputo es sobre horas EFECTIVAS trabajadas.
    """
    worked = annual_worked(records, policy, now)
    cap_hours = effective_annual_cap(worker, policy)
    cap = timedelta(hours=cap_hours)
    remaining = cap - worked
    ratio = (worked / cap) if cap.total_seconds() > 0 else 0.0
    start, end = annual_window(now)
    return {
        "worked": worked,
        "cap": cap,
        "cap_hours": cap_hours,
        "remaining": remaining,
        "ratio": ratio,
        "exceeded": worked > cap,
        "near": ratio >= ANNUAL_WARNING_RATIO,
        "year": start.year,
        "start": start,
        "end": end,
    }


def classify_overtime(
    records: list[_Record],
    policy: _Policy,
    now: datetime,
    relation_type: str = "ordinaria",
) -> dict:
    """Reparte el efectivo del periodo en ordinarias/extra/complementarias (REQ-08,12,26).

    El exceso se mide SOBRE EL PERIODO (no por día): un día largo compensado con días
    cortos dentro del mismo periodo no genera horas extra. La jornada ordinaria del periodo
    la fija `time_policy.ordinary_hours_per_period` (ajustable en runtime, REQ-13).

    REQ-26 (desglose): en un contrato a TIEMPO PARCIAL el exceso sobre la jornada pactada NO
    son horas extra sino COMPLEMENTARIAS (régimen distinto: pactadas, con límites y preaviso).
    Para `relation_type='tiempo_parcial'` el exceso se etiqueta como `complementarias` y
    `extra` queda a cero; en cualquier otra relación, al revés.
    """
    summary = period_summary(records, policy, now)
    efectivo = summary["efectivo"]
    ordinary = timedelta(hours=float(policy.ordinary_hours_per_period))
    exceso = max(efectivo - ordinary, timedelta(0))
    ordinarias = min(efectivo, ordinary)
    if relation_type == "tiempo_parcial":
        extra = timedelta(0)
        complementarias = exceso
    else:
        extra = exceso
        complementarias = timedelta(0)
    return {
        "efectivo": efectivo,
        "ordinarias": ordinarias,
        "extra": extra,
        "complementarias": complementarias,
        "ordinary": ordinary,
        "period": summary["period"],
        "start": summary["start"],
        "end": summary["end"],
    }
