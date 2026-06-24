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
from datetime import UTC, datetime, timedelta
from typing import Protocol


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


def journey_effective(journey: Journey, policy: _Policy) -> timedelta:
    """Tiempo efectivo de una jornada cerrada.

    Jornada abierta (sin check_out) → no computa (incidencia): devuelve 0.
    """
    if journey.check_out is None:
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
    """Ventana [inicio, fin) natural en UTC para el periodo de cómputo (REQ-12)."""
    now = now.astimezone(UTC)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "daily":
        return day_start, day_start + timedelta(days=1)
    if period == "weekly":
        start = day_start - timedelta(days=now.weekday())  # lunes
        return start, start + timedelta(days=7)
    # monthly (default)
    start = day_start.replace(day=1)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end


def period_summary(records: list[_Record], policy: _Policy, now: datetime) -> dict:
    """Suma el tiempo efectivo de las jornadas cerradas dentro del periodo actual.

    El reparto ordinarias/extra se deja a Fase 3; aquí solo el agregado efectivo.
    """
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
