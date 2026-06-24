"""Derecho a la desconexión digital (REQ-26). Lógica pura, sin BD.

La empresa debe garantizar la desconexión digital fuera de la jornada (art. 88 LOPDGDD /
art. 18 LITSS). `time_policy` define una ventana laboral [desconexion_start, desconexion_end);
un fichaje o acceso FUERA de esa ventana es "off-hours" y debe dejar constancia (alerta
`off_hours`, REQ-25) para revisión. No se bloquea: el trabajo puntual justificado es legítimo,
pero queda trazado.

La ventana puede cruzar medianoche (p.ej. 22:00..06:00) — se contempla. Si la política no
configura ventana (ambos NULL), no hay control de desconexión y nada se considera off-hours.
"""

from __future__ import annotations

from datetime import UTC, datetime, time
from typing import Protocol


class _Policy(Protocol):
    desconexion_start: time | None
    desconexion_end: time | None


def is_off_hours(dt: datetime, policy: _Policy) -> bool:
    """True si `dt` cae FUERA de la ventana laboral configurada (REQ-26).

    Devuelve False si la ventana no está configurada (sin control de desconexión). Soporta
    ventanas que cruzan medianoche. Se compara en hora UTC (coherente con el sellado).
    """
    start = policy.desconexion_start
    end = policy.desconexion_end
    if start is None or end is None:
        return False
    now_t = dt.astimezone(UTC).time()
    if start <= end:
        # Ventana normal dentro del mismo día: dentro si start <= t < end.
        within = start <= now_t < end
    else:
        # Ventana que cruza medianoche (p.ej. 22:00..06:00): dentro si t >= start o t < end.
        within = now_t >= start or now_t < end
    return not within
