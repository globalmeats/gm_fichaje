"""Detección de incumplimientos del horario esperado (petición de la gestora). Lógica pura.

Objetivo: que la gestora vea de un vistazo qué días se trabajó por debajo de la jornada
esperada (8 h/día todo el año, ver `schedule.expected_daily_min`). NO aplica a horario flexible
(su cómputo se reparte en el periodo pactado, REQ-29) ni a tiempo parcial (su control es el
tope anual prorrateado, no la jornada diaria). Ignora fines de semana y festivos.

El descanso de comida NO se policía por tramo (puede no ser seguido): solo cuenta la jornada
efectiva del día frente a la esperada.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.core.time import to_madrid
from app.domain.hours import Journey, journey_coherent, journey_effective
from app.domain.schedule import expected_daily_min


class _Policy:  # pragma: no cover - documentación de duck typing
    pause_computable_default: bool


@dataclass
class ScheduleIssue:
    """Un día laborable cuya jornada efectiva quedó por debajo de la esperada."""

    day: date
    worked_min: int
    expected_min: int


def schedule_issues(
    journeys: list[Journey],
    policy: _Policy,
    festivos: set[date],
    *,
    flexible: bool = False,
    part_time: bool = False,
) -> list[ScheduleIssue]:
    """Días (laborables, no festivos) con jornada efectiva por debajo de la esperada.

    Suma la jornada efectiva por día natural (hora de Madrid) por si hubiera varias jornadas
    en el mismo día; compara el total con `expected_daily_min(day)`. Flexibles y tiempo parcial
    quedan exentos del control diario.
    """
    if flexible or part_time:
        return []
    worked_by_day: dict[date, int] = {}
    for j in journeys:
        if j.check_out is None or not journey_coherent(j):
            continue
        day = to_madrid(j.check_in).date()
        if day.weekday() >= 5 or day in festivos:
            continue
        worked_by_day[day] = worked_by_day.get(day, 0) + int(
            journey_effective(j, policy).total_seconds() // 60
        )
    issues: list[ScheduleIssue] = []
    for day in sorted(worked_by_day):
        expected = expected_daily_min(day)
        if worked_by_day[day] < expected:
            issues.append(
                ScheduleIssue(day=day, worked_min=worked_by_day[day], expected_min=expected)
            )
    return issues
