"""Resolución de la jornada efectiva por trabajador (REQ-27, REQ-29). Lógica pura, sin BD.

La jornada pactada, el tope anual y los días de vacaciones son POR TRABAJADOR, pero el
trabajador puede dejarlos sin fijar (NULL) y entonces se usa el default global de
`time_policy` (fallback). Aquí se centraliza esa resolución para que API, dominio e informes
la calculen igual.
"""

from __future__ import annotations

from typing import Protocol


class _Worker(Protocol):
    weekly_hours: float | None
    annual_hours_cap: float | None


class _Policy(Protocol):
    annual_hours_cap: float
    annual_vacation_days: float


def effective_annual_cap(worker: _Worker, policy: _Policy) -> float:
    """Tope anual del trabajador, o el default global del convenio si no lo tiene fijado."""
    if worker.annual_hours_cap is not None:
        return float(worker.annual_hours_cap)
    return float(policy.annual_hours_cap)


def effective_weekly_hours(worker: _Worker, policy: _Policy) -> float | None:
    """Jornada semanal pactada del trabajador (None si no se ha fijado: no hay default global)."""
    if worker.weekly_hours is not None:
        return float(worker.weekly_hours)
    return None


def effective_vacation_days(worker: _Worker, policy: _Policy) -> float:
    """Días de vacaciones del trabajador.

    Hoy el cupo de vacaciones es global (convenio); se deja la firma por-trabajador para un
    override futuro sin tocar las llamadas.
    """
    return float(policy.annual_vacation_days)
