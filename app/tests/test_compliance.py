"""Incumplimientos del horario esperado (control de la gestora). Lógica pura, sin BD."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.domain.compliance import schedule_issues
from app.domain.hours import Journey
from app.domain.schedule import expected_daily_min


@dataclass
class _Policy:
    pause_computable_default: bool = True


def _journey(y: int, m: int, d: int, h_in: int, h_out: int) -> Journey:
    """Jornada cerrada de `h_in` a `h_out` (hora UTC) el día dado."""
    return Journey(
        check_in=datetime(y, m, d, h_in, tzinfo=UTC),
        check_out=datetime(y, m, d, h_out, tzinfo=UTC),
    )


def test_expected_daily_min_agosto_intensiva():
    from datetime import date

    assert expected_daily_min(date(2026, 7, 15)) == 480   # estándar 8 h
    assert expected_daily_min(date(2026, 8, 15)) == 360   # agosto 6 h


def test_short_day_is_flagged():
    # Miércoles 8-jul-2026 (laborable, no festivo): 6 h trabajadas < 8 h esperadas.
    issues = schedule_issues([_journey(2026, 7, 8, 6, 12)], _Policy(), set())
    assert len(issues) == 1
    assert issues[0].worked_min == 360 and issues[0].expected_min == 480


def test_full_day_not_flagged():
    # 8 h justas -> no es incumplimiento.
    issues = schedule_issues([_journey(2026, 7, 8, 6, 14)], _Policy(), set())
    assert issues == []


def test_flexible_and_part_time_exempt():
    short = [_journey(2026, 7, 8, 6, 8)]  # 2 h
    assert schedule_issues(short, _Policy(), set(), flexible=True) == []
    assert schedule_issues(short, _Policy(), set(), part_time=True) == []


def test_weekend_and_festivo_ignored():
    from datetime import date

    # Sábado 11-jul-2026 -> ignorado aunque sea corto.
    assert schedule_issues([_journey(2026, 7, 11, 6, 8)], _Policy(), set()) == []
    # Miércoles marcado como festivo -> ignorado.
    festivos = {date(2026, 7, 8)}
    assert schedule_issues([_journey(2026, 7, 8, 6, 8)], _Policy(), festivos) == []


def test_agosto_uses_intensive_expectation():
    # 6 h un día de agosto -> cumple (esperado 6 h); 5 h -> incumple.
    assert schedule_issues([_journey(2026, 8, 5, 6, 12)], _Policy(), set()) == []
    issues = schedule_issues([_journey(2026, 8, 5, 6, 11)], _Policy(), set())
    assert len(issues) == 1 and issues[0].expected_min == 360


def test_same_day_journeys_are_summed():
    # Dos jornadas el mismo día que suman 8 h -> no incumple.
    two = [_journey(2026, 7, 8, 6, 10), _journey(2026, 7, 8, 11, 15)]
    assert schedule_issues(two, _Policy(), set()) == []
