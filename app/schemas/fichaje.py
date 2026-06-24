"""Esquemas Pydantic v2 para el fichaje (REQ-01, REQ-07, REQ-09).

El cliente NUNCA envía la hora: la pone el servidor (REQ-15). Desde Fase 2 se aceptan los
6 tipos de evento (check/break/travel) y se expone el tiempo efectivo vía `/summary`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class FichajeEventRequest(BaseModel):
    event_type: Literal[
        "check_in", "check_out", "break_start", "break_end", "travel_start", "travel_end"
    ]
    modalidad: Literal["presencial", "teletrabajo", "movil"] = "presencial"
    source: Literal["web", "kiosk", "mobile", "offline_sync"] = "web"
    # Solo se lee en travel_*. Polaridad: true = ese desplazamiento computa como tiempo
    # efectivo (no se resta); false = no computa (se resta). Por defecto computa.
    travel_computes: bool = True


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


class JourneySummary(BaseModel):
    """Desglose de una jornada de hoy (en minutos)."""

    check_in: datetime
    check_out: datetime | None
    bruto_min: int
    pausa_computable_min: int
    travel_no_computa_min: int
    efectivo_min: int
    open: bool = Field(..., description="Jornada sin check_out: incidencia, no computa.")


class PeriodSummary(BaseModel):
    period: str
    start: datetime
    end: datetime
    efectivo_min: int


class SummaryResponse(BaseModel):
    today: list[JourneySummary]
    period: PeriodSummary
