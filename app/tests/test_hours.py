"""Cálculo de tiempo efectivo (REQ-07, REQ-09, REQ-12). Unit, sin BD."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.domain.hours import (
    journey_effective,
    period_summary,
    period_window,
    reconstruct_journeys,
)


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


def _at(h: int, m: int = 0) -> datetime:
    return datetime(2026, 6, 24, h, m, tzinfo=UTC)


def _minutes(td: timedelta) -> int:
    return int(td.total_seconds() // 60)


def test_simple_journey_effective_equals_gross():
    recs = [_Rec("check_in", _at(9)), _Rec("check_out", _at(17))]
    journeys = reconstruct_journeys(recs)
    assert len(journeys) == 1
    assert _minutes(journey_effective(journeys[0], _Policy())) == 8 * 60


def test_computable_pause_is_subtracted():
    recs = [
        _Rec("check_in", _at(9)),
        _Rec("break_start", _at(13)),
        _Rec("break_end", _at(14)),
        _Rec("check_out", _at(17)),
    ]
    j = reconstruct_journeys(recs)[0]
    # 8h bruto − 1h pausa computable = 7h.
    assert _minutes(journey_effective(j, _Policy(pause_computable_default=True))) == 7 * 60


def test_non_computable_pause_is_not_subtracted():
    recs = [
        _Rec("check_in", _at(9)),
        _Rec("break_start", _at(13)),
        _Rec("break_end", _at(14)),
        _Rec("check_out", _at(17)),
    ]
    j = reconstruct_journeys(recs)[0]
    # policy=false → la pausa NO resta: 8h.
    assert _minutes(journey_effective(j, _Policy(pause_computable_default=False))) == 8 * 60


def test_travel_not_computing_is_subtracted():
    recs = [
        _Rec("check_in", _at(9)),
        _Rec("travel_start", _at(12), travel_computes=False),
        _Rec("travel_end", _at(13), travel_computes=False),
        _Rec("check_out", _at(17)),
    ]
    j = reconstruct_journeys(recs)[0]
    # El desplazamiento de 1h NO computa → se resta: 7h.
    assert _minutes(journey_effective(j, _Policy())) == 7 * 60
    assert len(j.travels) == 1
    assert j.travels[0][2] is False


def test_travel_computing_is_not_subtracted():
    recs = [
        _Rec("check_in", _at(9)),
        _Rec("travel_start", _at(12), travel_computes=True),
        _Rec("travel_end", _at(13), travel_computes=True),
        _Rec("check_out", _at(17)),
    ]
    j = reconstruct_journeys(recs)[0]
    # travel_computes=true → computa → NO se resta: 8h.
    assert _minutes(journey_effective(j, _Policy())) == 8 * 60


def test_open_journey_marked_and_not_computed():
    recs = [_Rec("check_in", _at(9))]
    j = reconstruct_journeys(recs)[0]
    assert j.open is True
    assert journey_effective(j, _Policy()) == timedelta(0)


def test_split_shift_is_two_journeys():
    recs = [
        _Rec("check_in", _at(9)),
        _Rec("check_out", _at(13)),
        _Rec("check_in", _at(15)),
        _Rec("check_out", _at(19)),
    ]
    journeys = reconstruct_journeys(recs)
    assert len(journeys) == 2
    assert _minutes(journey_effective(journeys[0], _Policy())) == 4 * 60
    assert _minutes(journey_effective(journeys[1], _Policy())) == 4 * 60


def test_period_window_monthly():
    start, end = period_window(_at(10), "monthly")
    assert start == datetime(2026, 6, 1, tzinfo=UTC)
    assert end == datetime(2026, 7, 1, tzinfo=UTC)


def test_period_window_weekly_starts_monday():
    # 2026-06-24 es miércoles → la semana empieza el lunes 22.
    start, end = period_window(_at(10), "weekly")
    assert start == datetime(2026, 6, 22, tzinfo=UTC)
    assert end == datetime(2026, 6, 29, tzinfo=UTC)


def test_period_summary_sums_closed_journeys():
    recs = [
        _Rec("check_in", _at(9)),
        _Rec("check_out", _at(17)),  # 8h, dentro del mes
    ]
    out = period_summary(recs, _Policy(computation_period="monthly"), _at(20))
    assert _minutes(out["efectivo"]) == 8 * 60
    assert out["period"] == "monthly"
