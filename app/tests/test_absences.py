"""Lógica pura de ausencias: días, horas, solape, saldo de vacaciones (REQ-28). Sin BD."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time

from app.domain.absences import (
    absence_hours,
    covers,
    leave_days,
    overlaps,
    vacation_balance,
    vacation_days_taken,
)


@dataclass
class _Absence:
    absence_type: str = "vacaciones"
    status: str = "aprobada"
    start_date: date = date(2026, 1, 1)
    end_date: date = date(2026, 1, 1)
    start_time: time | None = None
    end_time: time | None = None


def test_leave_days_inclusive_calendar():
    # Lun 5 a Vie 9 de enero de 2026 = 5 días naturales y 5 laborables.
    assert leave_days(date(2026, 1, 5), date(2026, 1, 9), working_only=False) == 5
    assert leave_days(date(2026, 1, 5), date(2026, 1, 9), working_only=True) == 5


def test_leave_days_skips_weekend():
    # Vie 9 a Lun 12: 4 naturales, 2 laborables (vie y lun).
    assert leave_days(date(2026, 1, 9), date(2026, 1, 12), working_only=False) == 4
    assert leave_days(date(2026, 1, 9), date(2026, 1, 12), working_only=True) == 2


def test_leave_days_inverted_range_is_zero():
    assert leave_days(date(2026, 1, 9), date(2026, 1, 5)) == 0


def test_absence_hours_full_day_is_none():
    assert absence_hours(_Absence()) is None


def test_absence_hours_hourly():
    a = _Absence(start_time=time(9, 0), end_time=time(11, 30))
    assert absence_hours(a) == 2.5


def test_vacation_days_taken_only_counts_year_and_active():
    absences = [
        _Absence(start_date=date(2026, 1, 5), end_date=date(2026, 1, 9)),  # 5 lab
        _Absence(
            absence_type="vacaciones",
            status="cancelada",
            start_date=date(2026, 2, 2),
            end_date=date(2026, 2, 6),
        ),  # cancelada -> no cuenta
        _Absence(
            absence_type="baja",
            start_date=date(2026, 3, 2),
            end_date=date(2026, 3, 6),
        ),  # baja -> no es vacaciones
        _Absence(start_date=date(2025, 12, 29), end_date=date(2025, 12, 31)),  # otro año
    ]
    assert vacation_days_taken(absences, 2026) == 5


def test_vacation_days_taken_clips_to_year_boundary():
    # Rango que cruza fin de año: solo cuenta lo que cae en 2026.
    absences = [_Absence(start_date=date(2025, 12, 29), end_date=date(2026, 1, 2))]
    # 2026-01-01 (jue, festivo no contemplado) y 2026-01-02 (vie) = 2 laborables.
    assert vacation_days_taken(absences, 2026) == 2


def test_vacation_balance():
    bal = vacation_balance(22, 5)
    assert bal == {"entitled": 22, "taken": 5, "remaining": 17}


def test_overlaps_full_day_dates():
    existing = [_Absence(start_date=date(2026, 1, 5), end_date=date(2026, 1, 9))]
    assert overlaps(date(2026, 1, 8), date(2026, 1, 10), None, None, existing) is True
    assert overlaps(date(2026, 1, 10), date(2026, 1, 12), None, None, existing) is False


def test_overlaps_ignores_inactive():
    existing = [
        _Absence(
            status="cancelada",
            start_date=date(2026, 1, 5),
            end_date=date(2026, 1, 9),
        )
    ]
    assert overlaps(date(2026, 1, 6), date(2026, 1, 7), None, None, existing) is False


def test_overlaps_hourly_same_day_only_when_times_cross():
    existing = [
        _Absence(
            absence_type="permiso",
            start_date=date(2026, 1, 5),
            end_date=date(2026, 1, 5),
            start_time=time(9, 0),
            end_time=time(11, 0),
        )
    ]
    # Misma fecha, franja que NO cruza -> no solapa.
    assert (
        overlaps(date(2026, 1, 5), date(2026, 1, 5), time(11, 0), time(12, 0), existing)
        is False
    )
    # Misma fecha, franja que cruza -> solapa.
    assert (
        overlaps(date(2026, 1, 5), date(2026, 1, 5), time(10, 0), time(12, 0), existing)
        is True
    )


def test_overlaps_full_day_vs_hourly_same_day():
    # Una de día completo contra una por horas el mismo día -> basta el solape de fechas.
    existing = [
        _Absence(
            absence_type="permiso",
            start_date=date(2026, 1, 5),
            end_date=date(2026, 1, 5),
            start_time=time(9, 0),
            end_time=time(11, 0),
        )
    ]
    assert overlaps(date(2026, 1, 5), date(2026, 1, 5), None, None, existing) is True


def test_covers():
    a = _Absence(start_date=date(2026, 1, 5), end_date=date(2026, 1, 9))
    assert covers(a, date(2026, 1, 7)) is True
    assert covers(a, date(2026, 1, 10)) is False
    inactive = _Absence(
        status="rechazada", start_date=date(2026, 1, 5), end_date=date(2026, 1, 9)
    )
    assert covers(inactive, date(2026, 1, 7)) is False
