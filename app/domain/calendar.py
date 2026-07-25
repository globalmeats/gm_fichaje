"""Calendario anual de vacaciones (REQ-28). Lógica pura, sin BD.

Construye la rejilla de 12 meses de un año con, por día: el conjunto de trabajadores de
vacaciones (APROBADAS) y si es festivo de la Comunidad de Madrid. Un día con N trabajadores
se pinta con N franjas de color (degradado duro); 1 trabajador, color sólido. Solo vacaciones:
las bajas/permisos (datos sensibles) NUNCA entran aquí (el calendario lo ven todos).

Los festivos vienen de la librería `holidays` (nacionales + autonómicos de Madrid), que se
actualiza sola por año; los locales/municipales se pasan aparte (config), si se quieren.
"""

from __future__ import annotations

import calendar as _calendar
from dataclasses import dataclass, field
from datetime import date

import holidays as _holidays

# Paleta de colores por trabajador (evita el rojo "seal" y el verde/ámbar de estado).
PALETTE = [
    "#2F6FED", "#E08A1E", "#C0389A", "#2F9E8F", "#7A5CD0",
    "#B5651D", "#1F8FBF", "#D14D8B", "#5B8C2A", "#8A6D3B",
]

_MONTH_NAMES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]
_WEEK_HEADER = ["Lu", "Ma", "Mi", "Ju", "Vi", "Sá", "Do"]


def worker_color(index: int) -> str:
    return PALETTE[index % len(PALETTE)]


def _gradient(colors: list[str]) -> str:
    """CSS de fondo para un día: sólido si 1 color, franjas iguales si varios."""
    if len(colors) == 1:
        return colors[0]
    n = len(colors)
    stops = []
    for i, c in enumerate(colors):
        stops.append(f"{c} {i * 100 // n}% {(i + 1) * 100 // n}%")
    return f"linear-gradient(90deg, {', '.join(stops)})"


@dataclass
class DayCell:
    day: int | None            # número de día (None si no pertenece al mes)
    date: date | None = None
    festivo: str | None = None  # nombre del festivo si lo es
    weekend: bool = False
    colors: list[str] = field(default_factory=list)  # colores de trabajadores de vacaciones

    @property
    def background(self) -> str:
        return _gradient(self.colors) if self.colors else ""


@dataclass
class MonthGrid:
    name: str
    weeks: list[list[DayCell]]


def madrid_holidays(year: int, local: dict[date, str] | None = None) -> dict[date, str]:
    """Festivos nacionales + Comunidad de Madrid del año, más locales opcionales (config)."""
    result = dict(_holidays.Spain(subdiv="MD", years=year))
    if local:
        result.update(local)
    return result


def build_year(
    year: int,
    vacations_by_worker: dict[str, list[tuple[date, date]]],
    color_by_worker: dict[str, str],
    local_holidays: dict[date, str] | None = None,
) -> tuple[list[MonthGrid], dict[date, str]]:
    """Rejilla de 12 meses. `vacations_by_worker`: worker_id -> lista de rangos (inicio,fin)
    de vacaciones aprobadas. Devuelve (meses, festivos)."""
    fest = madrid_holidays(year, local_holidays)

    # Mapa día -> colores (en orden estable de trabajador para que las franjas no bailen).
    day_colors: dict[date, list[str]] = {}
    for worker_id in sorted(vacations_by_worker, key=lambda w: color_by_worker.get(w, "")):
        color = color_by_worker.get(worker_id)
        if not color:
            continue
        for start, end in vacations_by_worker[worker_id]:
            d = max(start, date(year, 1, 1))
            last = min(end, date(year, 12, 31))
            while d <= last:
                day_colors.setdefault(d, [])
                if color not in day_colors[d]:
                    day_colors[d].append(color)
                d = date.fromordinal(d.toordinal() + 1)

    cal = _calendar.Calendar(firstweekday=0)  # lunes primero
    months: list[MonthGrid] = []
    for month in range(1, 13):
        weeks: list[list[DayCell]] = []
        for week in cal.monthdatescalendar(year, month):
            row: list[DayCell] = []
            for d in week:
                if d.month != month:
                    row.append(DayCell(day=None))
                    continue
                row.append(
                    DayCell(
                        day=d.day, date=d, festivo=fest.get(d),
                        weekend=d.weekday() >= 5, colors=day_colors.get(d, []),
                    )
                )
            weeks.append(row)
        months.append(MonthGrid(name=_MONTH_NAMES[month - 1], weeks=weeks))
    return months, fest
