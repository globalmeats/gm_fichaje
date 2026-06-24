"""Esquemas Pydantic v2 para el fichaje (REQ-01).

El cliente NUNCA envía la hora: la pone el servidor (REQ-15). En Fase 1 solo se aceptan
check_in/check_out; pausas y desplazamientos llegan en Fase 2.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class FichajeEventRequest(BaseModel):
    event_type: Literal["check_in", "check_out"]
    modalidad: Literal["presencial", "teletrabajo", "movil"] = "presencial"
    source: Literal["web", "kiosk", "mobile", "offline_sync"] = "web"


class FichajeEventResponse(BaseModel):
    id: str
    seq: int
    event_type: str
    occurred_at: datetime
    prev_hash: str
    hash: str


class TodayEvent(BaseModel):
    seq: int
    event_type: str
    occurred_at: datetime


class TodayResponse(BaseModel):
    state: str = Field(..., description="Estado actual de la jornada reconstruido del histórico.")
    events: list[TodayEvent]
