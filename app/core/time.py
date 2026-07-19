"""Utilidades de tiempo (UTC) y semilla de sellado encadenado.

REQ-15 (🟡): los registros llevan timestamp del servidor en UTC + hash encadenado.
Aquí dejamos las primitivas (hora UTC del servidor, formato ISO-8601 y el cálculo de
hash de cadena). La cadena de hash completa sobre `time_record` vive en Fase 1
(`app/audit/chain.py`); este módulo es la base reutilizable.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

# Zona local de la empresa. El almacenamiento, el sellado/hash y los INSTANTES siguen en UTC;
# las FRONTERAS de calendario (día/semana/mes/año para el cómputo de horas) se calculan en
# hora local de Madrid y se convierten a UTC, para que un fichaje a las 23:30 locales cuente
# en su día/mes real y no en el siguiente (BUG-02).
MADRID = ZoneInfo("Europe/Madrid")


def utc_now() -> datetime:
    """Hora actual del servidor, timezone-aware en UTC. Nunca confiar en el cliente."""
    return datetime.now(UTC)


def iso8601(dt: datetime) -> str:
    """Formatea un datetime a ISO-8601 (el cliente formatea a su zona local)."""
    return dt.astimezone(UTC).isoformat()


def to_madrid(dt: datetime) -> datetime:
    """Convierte un datetime UTC a hora local de Madrid (DST automático).

    Solo para presentación: nunca se aplica al valor almacenado, al payload del hash
    ni al cálculo de horas (todo eso permanece en UTC).
    """
    if dt.tzinfo is None:  # defensivo: los datetimes de la BD vienen aware (timestamptz)
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(MADRID)


def madrid_midnight_utc(d: date) -> datetime:
    """Instante UTC de la medianoche local de Madrid del día `d`.

    La medianoche siempre existe y es inequívoca en España (los saltos DST ocurren a las
    02:00/03:00), así que no hay ambigüedad de fold.
    """
    return datetime(d.year, d.month, d.day, tzinfo=MADRID).astimezone(UTC)


def madrid_today_start(now: datetime) -> datetime:
    """Inicio del día local de Madrid que contiene `now`, devuelto como instante UTC."""
    return madrid_midnight_utc(to_madrid(now).date())


def madrid_date(now: datetime) -> date:
    """Fecha local de Madrid de `now` (para calcular fronteras de semana/mes/año)."""
    return to_madrid(now).date()


def add_months(d: date, months: int) -> date:
    """Suma `months` meses a `d`, fijando el día 1 (uso para fronteras de mes)."""
    total = (d.year * 12 + (d.month - 1)) + months
    return date(total // 12, total % 12 + 1, 1)


def chain_hash(prev_hash: str | None, payload: str) -> str:
    """Hash SHA-256 que encadena `payload` con el `prev_hash` del registro anterior.

    Semilla del sellado encadenado (REQ-15). El primer registro de una cadena usa
    prev_hash vacío. La integración con `time_record` se hace en Fase 1.
    """
    data = f"{prev_hash or ''}|{payload}".encode()
    return hashlib.sha256(data).hexdigest()
