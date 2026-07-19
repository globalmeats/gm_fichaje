"""Cómputo del tope anual de jornada (REQ-27). Unit, sin BD."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.domain.hours import annual_status, annual_window, annual_worked


@dataclass
class _Rec:
    event_type: str
    occurred_at: datetime
    travel_computes: bool = True


@dataclass
class _Policy:
    pause_computable_default: bool = True
    computation_period: str = "monthly"
    ordinary_hours_per_period: float = 160
    annual_hours_cap: float = 1760
    annual_vacation_days: float = 22


@dataclass
class _Worker:
    weekly_hours: float | None = None
    annual_hours_cap: float | None = None


def _day(month: int, day: int, h: int) -> datetime:
    return datetime(2026, month, day, h, tzinfo=UTC)


def test_annual_window_is_calendar_year():
    # 1 de enero a medianoche de Madrid (invierno = UTC+1 → 23:00 UTC del 31 dic) (BUG-02).
    start, end = annual_window(_day(6, 24, 10))
    assert start == datetime(2025, 12, 31, 23, tzinfo=UTC)
    assert end == datetime(2026, 12, 31, 23, tzinfo=UTC)


def test_annual_worked_only_counts_this_year_closed_journeys():
    recs = [
        # Año anterior: NO cuenta.
        _Rec("check_in", datetime(2025, 12, 31, 9, tzinfo=UTC)),
        _Rec("check_out", datetime(2025, 12, 31, 17, tzinfo=UTC)),
        # Este año: 8h.
        _Rec("check_in", _day(1, 5, 9)),
        _Rec("check_out", _day(1, 5, 17)),
        # Jornada abierta: NO computa.
        _Rec("check_in", _day(2, 2, 9)),
    ]
    worked = annual_worked(recs, _Policy(), _day(6, 1, 12))
    assert worked.total_seconds() / 3600 == 8


def test_annual_status_remaining_and_flags():
    # Una jornada de 8h con cap muy bajo (10h) → ratio 0.8, ni cerca ni superado.
    recs = [_Rec("check_in", _day(1, 5, 9)), _Rec("check_out", _day(1, 5, 17))]
    st = annual_status(recs, _Worker(annual_hours_cap=10), _Policy(), _day(6, 1, 12))
    assert st["cap_hours"] == 10
    assert round(st["worked"].total_seconds() / 3600, 1) == 8.0
    assert round(st["remaining"].total_seconds() / 3600, 1) == 2.0
    assert st["exceeded"] is False
    assert st["near"] is False


def test_annual_status_near_and_exceeded():
    recs = [_Rec("check_in", _day(1, 5, 9)), _Rec("check_out", _day(1, 5, 19))]  # 10h
    # cap 10 → ratio 1.0 → near True, exceeded False (no estrictamente mayor).
    near = annual_status(recs, _Worker(annual_hours_cap=10), _Policy(), _day(6, 1, 12))
    assert near["near"] is True
    assert near["exceeded"] is False
    # cap 9 → superado.
    over = annual_status(recs, _Worker(annual_hours_cap=9), _Policy(), _day(6, 1, 12))
    assert over["exceeded"] is True
