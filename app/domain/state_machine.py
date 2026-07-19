"""Máquina de estados de la jornada (REQ-01).

El estado se DERIVA del histórico append-only de `time_record`, nunca de un campo
mutable (ver skill audit-trail / fichaje-domain). `reconstruct_state` pliega los eventos
en orden desde `IDLE`; `next_state` valida una transición concreta.

Fase 1 solo emite check_in/check_out, pero la tabla de transiciones cubre ya las 6
(pausas y desplazamientos) para no rehacerla en Fase 2.
"""

from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum


class State(StrEnum):
    IDLE = "IDLE"
    ABIERTA = "ABIERTA"
    EN_PAUSA = "EN_PAUSA"
    EN_DESPLAZAMIENTO = "EN_DESPLAZAMIENTO"


class InvalidTransition(Exception):
    """El evento no es válido desde el estado actual (-> 409 en la API)."""

    def __init__(self, state: State, event: str) -> None:
        self.state = state
        self.event = event
        super().__init__(f"Transición inválida: '{event}' desde {state.value}.")


# Tabla de transiciones (references/state-machine.md).
_TRANSITIONS: dict[State, dict[str, State]] = {
    State.IDLE: {
        "check_in": State.ABIERTA,
    },
    State.ABIERTA: {
        "break_start": State.EN_PAUSA,
        "travel_start": State.EN_DESPLAZAMIENTO,
        "check_out": State.IDLE,
    },
    State.EN_PAUSA: {
        "break_end": State.ABIERTA,
    },
    State.EN_DESPLAZAMIENTO: {
        "travel_end": State.ABIERTA,
    },
}


def next_state(current: State, event: str) -> State:
    """Estado resultante de aplicar `event` sobre `current`.

    Lanza `InvalidTransition` si la transición no está permitida (p. ej. doble check_in,
    o check_out sin jornada abierta).
    """
    allowed = _TRANSITIONS.get(current, {})
    if event not in allowed:
        raise InvalidTransition(current, event)
    return allowed[event]


def reconstruct_state(events: Iterable[str], *, strict: bool = True) -> State:
    """Reconstruye el estado actual plegando los `event_type` en orden desde IDLE.

    Cada check_out devuelve a IDLE, así que el resultado refleja la jornada abierta
    (los eventos tras el último check_out). El histórico válido lo garantiza la validación
    en escritura (atómica bajo lock, ver `audit.chain.append_event`).

    `strict=True` (escritura): ante un evento imposible lanza `InvalidTransition`. `strict=False`
    (lectura defensiva): ignora un evento incoherente y sigue, para que una vista NUNCA caiga a
    500 aunque el histórico llegara a estar corrupto por una vía inesperada.
    """
    state = State.IDLE
    for event in events:
        try:
            state = next_state(state, event)
        except InvalidTransition:
            if strict:
                raise
    return state
