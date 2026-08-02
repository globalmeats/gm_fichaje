"""Cálculo sobre ausencias: vacaciones, bajas y permisos (REQ-28). Lógica pura, sin BD.

Una ausencia aprobada justifica que no se fiche ese tiempo (`covers`). Las vacaciones se
contabilizan en días; los permisos por horas (cita médica) no consumen día de vacaciones sino
horas justificadas. Las vacaciones descuentan fines de semana y festivos de la Comunidad de
Madrid (nacionales + autonómicos), que se recalculan solos por año; ver `vacation_days_taken`
y `app.domain.calendar.festivos_set`.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Protocol

from app.domain.calendar import festivos_set


class _Absence(Protocol):
    absence_type: str
    status: str
    start_date: date
    end_date: date
    start_time: time | None
    end_time: time | None


def leave_days(
    start: date,
    end: date,
    *,
    working_only: bool = True,
    holidays: set[date] | None = None,
) -> int:
    """Número de días del rango [start, end] (ambos inclusive).

    `working_only=True` cuenta solo de lunes a viernes. `holidays` (si se pasa) excluye además
    esos días festivos. Un festivo que cae en fin de semana no resta dos veces.
    """
    if end < start:
        return 0
    total = 0
    day = start
    while day <= end:
        is_weekend = day.weekday() >= 5
        is_holiday = holidays is not None and day in holidays
        if (not working_only or not is_weekend) and not is_holiday:
            total += 1
        day += timedelta(days=1)
    return total


def absence_hours(absence: _Absence) -> float | None:
    """Horas de una ausencia por tramo horario (cita médica); `None` si es de día completo."""
    if absence.start_time is None or absence.end_time is None:
        return None
    start = datetime.combine(absence.start_date, absence.start_time)
    end = datetime.combine(absence.start_date, absence.end_time)
    delta = end - start
    return delta.total_seconds() / 3600 if delta.total_seconds() > 0 else 0.0


def _is_active(absence: _Absence) -> bool:
    """Una ausencia 'cuenta' si está aprobada o pendiente (no rechazada/cancelada)."""
    return absence.status in ("aprobada", "pendiente")


def vacation_days_taken(
    absences: list[_Absence], year: int, holidays: set[date] | None = None
) -> int:
    """Días de vacaciones (aprobadas/pendientes) que caen en el año natural dado.

    Excluye fines de semana y festivos. Si `holidays` es None se usan los festivos de la
    Comunidad de Madrid del año (nacionales + autonómicos), recalculados solos por año.
    """
    if holidays is None:
        holidays = festivos_set(year)
    total = 0
    for a in absences:
        if a.absence_type != "vacaciones" or not _is_active(a):
            continue
        start = max(a.start_date, date(year, 1, 1))
        end = min(a.end_date, date(year, 12, 31))
        total += leave_days(start, end, working_only=True, holidays=holidays)
    return total


def vacation_balance(entitled: float, taken: int) -> dict:
    """Saldo de vacaciones: derecho, consumidos y restantes."""
    return {
        "entitled": entitled,
        "taken": taken,
        "remaining": entitled - taken,
    }


def overlaps(
    start: date,
    end: date,
    start_time: time | None,
    end_time: time | None,
    existing: list[_Absence],
) -> bool:
    """¿El rango propuesto solapa con alguna ausencia activa?

    Solape de fechas para días completos. Si ambas ausencias son por horas EN EL MISMO día,
    además deben solapar las franjas horarias; si una es de día completo, basta el solape de
    fechas.
    """
    for a in existing:
        if not _is_active(a):
            continue
        if end < a.start_date or start > a.end_date:
            continue  # no hay solape de fechas
        # Solape de fechas confirmado. Si ambas son por horas en un único día, comparar franjas.
        both_hourly = (
            start_time is not None
            and end_time is not None
            and a.start_time is not None
            and a.end_time is not None
            and start == end == a.start_date == a.end_date
        )
        if both_hourly:
            if start_time < a.end_time and a.start_time < end_time:
                return True
            continue
        return True
    return False


def covers(absence: _Absence, day: date) -> bool:
    """¿Una ausencia activa cubre `day`? (tiempo justificado: no es fichaje faltante)."""
    return _is_active(absence) and absence.start_date <= day <= absence.end_date


# Máximo de personas que pueden estar de vacaciones a la vez (petición de oficina).
MAX_CONCURRENT_VACATIONS = 2


def concurrency_exceeded(
    start: date,
    end: date,
    others: list[tuple[date, date]],
    *,
    max_people: int = MAX_CONCURRENT_VACATIONS,
) -> bool:
    """¿Añadir una vacación en [start, end] dejaría a más de `max_people` personas a la vez?

    `others` son rangos (inicio, fin) de vacaciones ya existentes de OTROS trabajadores (se
    asume una entrada por trabajador; los rangos de un mismo trabajador no se solapan entre sí).
    Se cuenta, día a día del rango solicitado, cuántos otros coinciden; si en algún día ya hay
    `max_people` o más, el solicitante sería uno de más -> True (conflicto).
    """
    if end < start:
        return False
    day = start
    while day <= end:
        if sum(1 for s, e in others if s <= day <= e) >= max_people:
            return True
        day += timedelta(days=1)
    return False
