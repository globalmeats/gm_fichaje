"""Cálculo sobre ausencias: vacaciones, bajas y permisos (REQ-28). Lógica pura, sin BD.

Una ausencia aprobada justifica que no se fiche ese tiempo (`covers`). Las vacaciones se
contabilizan en días; los permisos por horas (cita médica) no consumen día de vacaciones sino
horas justificadas. El calendario de festivos queda fuera de alcance (DEFERRED): `leave_days`
con `working_only` solo descuenta fines de semana.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Protocol


class _Absence(Protocol):
    absence_type: str
    status: str
    start_date: date
    end_date: date
    start_time: time | None
    end_time: time | None


def leave_days(start: date, end: date, *, working_only: bool = True) -> int:
    """Número de días del rango [start, end] (ambos inclusive).

    `working_only=True` cuenta solo de lunes a viernes (no descuenta festivos: DEFERRED).
    """
    if end < start:
        return 0
    total = 0
    day = start
    while day <= end:
        if not working_only or day.weekday() < 5:
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


def vacation_days_taken(absences: list[_Absence], year: int) -> int:
    """Días de vacaciones (aprobadas/pendientes) que caen en el año natural dado."""
    total = 0
    for a in absences:
        if a.absence_type != "vacaciones" or not _is_active(a):
            continue
        start = max(a.start_date, date(year, 1, 1))
        end = min(a.end_date, date(year, 12, 31))
        total += leave_days(start, end, working_only=True)
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
