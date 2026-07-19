"""BUG-02/03: fronteras de cómputo y desconexión en hora de Madrid, no UTC."""

from __future__ import annotations

from datetime import UTC, datetime, time

from app.core.time import add_months, madrid_midnight_utc, madrid_today_start
from app.domain.desconexion import is_off_hours
from app.domain.hours import annual_window, period_window


class _Pol:
    def __init__(self, start, end):
        self.desconexion_start = start
        self.desconexion_end = end


def test_madrid_midnight_is_earlier_in_utc_in_summer():
    # 1 de julio: Madrid es UTC+2, así que la medianoche local son las 22:00 UTC del día previo.
    inst = madrid_midnight_utc(datetime(2026, 7, 1).date())
    assert inst == datetime(2026, 6, 30, 22, 0, tzinfo=UTC)


def test_month_boundary_uses_madrid_calendar():
    # Un instante a las 23:30 del 31 de julio en Madrid (21:30 UTC) pertenece a JULIO.
    now = datetime(2026, 7, 31, 21, 30, tzinfo=UTC)
    start, end = period_window(now, "monthly")
    assert start == madrid_midnight_utc(datetime(2026, 7, 1).date())
    assert end == madrid_midnight_utc(datetime(2026, 8, 1).date())
    assert start <= now < end


def test_today_start_of_late_night_event_is_same_madrid_day():
    # 00:30 UTC del 2 de julio = 02:30 Madrid del 2 de julio → el día es el 2, no el 1.
    now = datetime(2026, 7, 2, 0, 30, tzinfo=UTC)
    assert madrid_today_start(now) == madrid_midnight_utc(datetime(2026, 7, 2).date())


def test_annual_window_madrid():
    now = datetime(2026, 1, 1, 0, 30, tzinfo=UTC)  # 01:30 Madrid del 1 ene 2026 (invierno UTC+1)
    start, end = annual_window(now)
    assert start == madrid_midnight_utc(datetime(2026, 1, 1).date())
    assert end == madrid_midnight_utc(datetime(2027, 1, 1).date())


def test_add_months_rolls_year():
    assert add_months(datetime(2026, 12, 1).date(), 1) == datetime(2027, 1, 1).date()


def test_off_hours_window_is_madrid_local():
    pol = _Pol(time(8, 0), time(20, 0))  # jornada 08:00–20:00 hora de Madrid
    # 19:00 UTC en verano = 21:00 Madrid → fuera de jornada (off-hours).
    assert is_off_hours(datetime(2026, 7, 1, 19, 0, tzinfo=UTC), pol) is True
    # 10:00 UTC en verano = 12:00 Madrid → dentro de jornada.
    assert is_off_hours(datetime(2026, 7, 1, 10, 0, tzinfo=UTC), pol) is False
