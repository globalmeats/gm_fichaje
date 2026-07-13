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
    # Geolocalización PUNTUAL del instante del fichaje (REQ-20). Solo se almacena (cifrada) si
    # el trabajador tiene consentimiento y la modalidad es móvil; en otro caso se descarta.
    geo: str | None = None


class OfflineEventRequest(BaseModel):
    """Evento capturado SIN red y sincronizado a posteriori (REQ-22).

    Excepción deliberada y acotada a REQ-15 (hora de servidor): este evento conserva la hora
    REAL del fichaje (`occurred_at` del cliente), validada dentro de una ventana de tolerancia.
    `client_event_id` es la clave de idempotencia de la cola de sincronización (queue): reenviar
    el mismo evento no lo duplica.
    """

    event_type: Literal[
        "check_in", "check_out", "break_start", "break_end", "travel_start", "travel_end"
    ]
    occurred_at: datetime
    client_event_id: str = Field(..., min_length=1, max_length=200)
    modalidad: Literal["presencial", "teletrabajo", "movil"] = "presencial"
    travel_computes: bool = True
    geo: str | None = None


class FichajeEventResponse(BaseModel):
    id: str
    seq: int
    event_type: str
    occurred_at: datetime
    prev_hash: str
    hash: str


class SyncEventResponse(FichajeEventResponse):
    """Respuesta de `/fichaje/sync`. `deduplicated=True` si el evento ya estaba sincronizado."""

    deduplicated: bool = False


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


class AnnualSummary(BaseModel):
    """Estado del tope anual de jornada del trabajador (REQ-27)."""

    year: int
    worked_min: int
    cap_min: int
    remaining_min: int
    exceeded: bool
    near: bool


class VacationSummary(BaseModel):
    """Saldo de vacaciones del año en curso (autodisponibilidad, REQ-18/28)."""

    year: int
    entitled: float
    taken: int
    remaining: float


class SummaryResponse(BaseModel):
    today: list[JourneySummary]
    period: PeriodSummary
    annual: AnnualSummary
    vacation: VacationSummary
