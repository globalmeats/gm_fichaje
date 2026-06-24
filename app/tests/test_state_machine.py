"""Máquina de estados de la jornada (REQ-01). Unit, sin BD."""

from __future__ import annotations

import pytest

from app.domain.state_machine import (
    InvalidTransition,
    State,
    next_state,
    reconstruct_state,
)


def test_valid_transitions():
    assert next_state(State.IDLE, "check_in") == State.ABIERTA
    assert next_state(State.ABIERTA, "check_out") == State.IDLE
    assert next_state(State.ABIERTA, "break_start") == State.EN_PAUSA
    assert next_state(State.EN_PAUSA, "break_end") == State.ABIERTA
    assert next_state(State.ABIERTA, "travel_start") == State.EN_DESPLAZAMIENTO
    assert next_state(State.EN_DESPLAZAMIENTO, "travel_end") == State.ABIERTA


def test_double_check_in_invalid():
    with pytest.raises(InvalidTransition):
        next_state(State.ABIERTA, "check_in")


def test_check_out_without_open_invalid():
    with pytest.raises(InvalidTransition):
        next_state(State.IDLE, "check_out")


def test_reconstruct_empty_is_idle():
    assert reconstruct_state([]) == State.IDLE


def test_reconstruct_open_journey():
    assert reconstruct_state(["check_in"]) == State.ABIERTA
    assert reconstruct_state(["check_in", "check_out"]) == State.IDLE
    # Tras cerrar y reabrir, refleja la jornada abierta.
    assert reconstruct_state(["check_in", "check_out", "check_in"]) == State.ABIERTA
    assert reconstruct_state(["check_in", "break_start"]) == State.EN_PAUSA


def test_reconstruct_invalid_history_raises():
    with pytest.raises(InvalidTransition):
        reconstruct_state(["check_in", "check_in"])
