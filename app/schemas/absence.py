"""Esquemas Pydantic v2 para ausencias y justificantes (REQ-28).

El alta la hace solo el admin/gestora. La `baja` se registra SOLO con fechas/estado (sin dato
clínico). Un `permiso` exige subtipo del catálogo del convenio; puede ser de día(s) completo(s)
o por horas (cita médica). El binario del justificante NUNCA viaja en estos esquemas.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.db.models import ABSENCE_STATUSES, ABSENCE_TYPES, PERMISO_SUBTYPES


class AbsenceCreate(BaseModel):
    worker_id: uuid.UUID
    absence_type: str
    subtype: str | None = None
    start_date: date
    end_date: date
    start_time: time | None = None
    end_time: time | None = None
    status: str = "aprobada"
    note: str | None = None

    @model_validator(mode="after")
    def _check(self) -> AbsenceCreate:
        if self.absence_type not in ABSENCE_TYPES:
            raise ValueError(f"absence_type debe ser uno de {ABSENCE_TYPES}")
        if self.status not in ABSENCE_STATUSES:
            raise ValueError(f"status debe ser uno de {ABSENCE_STATUSES}")
        if self.end_date < self.start_date:
            raise ValueError("end_date no puede ser anterior a start_date")
        if self.absence_type == "permiso":
            if self.subtype not in PERMISO_SUBTYPES:
                raise ValueError(f"subtype de permiso debe ser uno de {PERMISO_SUBTYPES}")
        # Ausencia por horas: ambos tiempos, dentro de un único día y franja válida.
        has_start = self.start_time is not None
        has_end = self.end_time is not None
        if has_start != has_end:
            raise ValueError("start_time y end_time deben informarse juntos")
        if has_start and has_end:
            if self.start_date != self.end_date:
                raise ValueError("una ausencia por horas debe ser de un único día")
            if self.end_time <= self.start_time:
                raise ValueError("end_time debe ser posterior a start_time")
        return self


class AbsenceDocumentResponse(BaseModel):
    """Metadatos del justificante. NUNCA incluye el binario (que se sirve por descarga)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    content_type: str
    byte_size: int
    uploaded_at: datetime


class AbsenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    worker_id: uuid.UUID
    absence_type: str
    subtype: str | None
    start_date: date
    end_date: date
    start_time: time | None
    end_time: time | None
    status: str
    justified: bool
    note: str | None
    hours: float | None = None
    has_document: bool = False


class VacationBalanceResponse(BaseModel):
    year: int
    entitled: float
    taken: int
    remaining: float = Field(..., description="entitled - taken")
