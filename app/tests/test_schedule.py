"""Resolución de jornada por trabajador con fallback global (REQ-27, REQ-29). Unit, sin BD."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.schedule import (
    effective_annual_cap,
    effective_vacation_days,
    effective_weekly_hours,
)


@dataclass
class _Worker:
    weekly_hours: float | None = None
    annual_hours_cap: float | None = None


@dataclass
class _Policy:
    annual_hours_cap: float = 1760
    annual_vacation_days: float = 22


def test_annual_cap_uses_worker_override():
    assert effective_annual_cap(_Worker(annual_hours_cap=1000), _Policy()) == 1000


def test_annual_cap_falls_back_to_policy():
    assert effective_annual_cap(_Worker(annual_hours_cap=None), _Policy()) == 1760


def test_weekly_hours_worker_or_none():
    assert effective_weekly_hours(_Worker(weekly_hours=40), _Policy()) == 40
    assert effective_weekly_hours(_Worker(weekly_hours=None), _Policy()) is None


def test_vacation_days_from_policy():
    assert effective_vacation_days(_Worker(), _Policy(annual_vacation_days=30)) == 30
