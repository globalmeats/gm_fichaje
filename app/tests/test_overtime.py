"""Clasificación ordinarias/extra por periodo de cómputo (REQ-08, REQ-12). Unit, sin BD.

La clave legal (REQ-12): el exceso se mide SOBRE EL PERIODO, no por día. Un día largo
compensado con días cortos dentro del mismo periodo no genera horas extra.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.domain.hours import classify_overtime


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


def _minutes(td: timedelta) -> int:
    return int(td.total_seconds() // 60)


def _journey(day: int, hours: float) -> list[_Rec]:
    """check_in 8:00 / check_out 8:00+hours en 2026-06-`day` (UTC)."""
    ci = datetime(2026, 6, day, 8, 0, tzinfo=UTC)
    co = ci + timedelta(hours=hours)
    return [_Rec("check_in", ci), _Rec("check_out", co)]


def test_daily_excess_is_not_overtime_if_period_balances():
    """REQ-12: un día de 9h dentro de un mes que totaliza ≤ ordinaria NO es extra."""
    recs: list[_Rec] = []
    # 9h + 7h + 8h*17 = 16 + 136 = 152h en el mes, bajo las 160h ordinarias.
    recs += _journey(1, 9)
    recs += _journey(2, 7)
    for d in range(3, 20):
        recs += _journey(d, 8)
    out = classify_overtime(
        recs, _Policy(ordinary_hours_per_period=160), datetime(2026, 6, 20, 12, tzinfo=UTC)
    )
    assert _minutes(out["efectivo"]) == 152 * 60
    assert _minutes(out["extra"]) == 0
    assert _minutes(out["ordinarias"]) == 152 * 60


def test_period_excess_is_overtime():
    """Si el efectivo del periodo supera la ordinaria, el exceso es extra."""
    recs: list[_Rec] = []
    # 20 días * 8.5h = 170h en el mes; ordinaria 160h → 10h extra.
    for d in range(1, 21):
        recs += _journey(d, 8.5)
    out = classify_overtime(
        recs, _Policy(ordinary_hours_per_period=160), datetime(2026, 6, 21, 12, tzinfo=UTC)
    )
    assert _minutes(out["efectivo"]) == 170 * 60
    assert _minutes(out["ordinarias"]) == 160 * 60
    assert _minutes(out["extra"]) == 10 * 60


def test_weekly_period_respected():
    """Con periodo semanal, solo cuenta la semana de la referencia."""
    recs: list[_Rec] = []
    # Semana del lunes 2026-06-22: lun-vie 9h = 45h; ordinaria 40h → 5h extra.
    for d in range(22, 27):
        recs += _journey(d, 9)
    # Una jornada de la semana anterior no debe contar.
    recs += _journey(19, 9)
    out = classify_overtime(
        recs,
        _Policy(computation_period="weekly", ordinary_hours_per_period=40),
        datetime(2026, 6, 24, 12, tzinfo=UTC),
    )
    assert _minutes(out["efectivo"]) == 45 * 60
    assert _minutes(out["extra"]) == 5 * 60
    assert out["period"] == "weekly"
