"""Esquemas del informe de jornada exportable / portal del trabajador (REQ-04, REQ-18, REQ-19).

El informe es VERIFICABLE: incluye el sellado (hash/prev_hash) de cada registro y, junto a cada
uno, sus correcciones (skill audit-trail §3: mostrar el original Y sus correcciones, nunca solo
el valor corregido), más la totalización del periodo. Se reutiliza tal cual para el JSON del
portal (`GET /me/records`) y como fuente de los exports CSV/PDF.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time

from pydantic import BaseModel


class ExportAbsenceRow(BaseModel):
    """Ausencia del periodo en el informe. NUNCA incluye el binario del justificante."""

    absence_type: str
    subtype: str | None
    start_date: date
    end_date: date
    start_time: time | None
    end_time: time | None
    status: str
    justified: bool
    hours: float | None = None
    has_document: bool = False


class ExportCorrectionRow(BaseModel):
    seq: int
    field: str
    corrected_value: str
    reason: str
    author_id: uuid.UUID
    occurred_at: datetime
    hash: str


class ExportRecordRow(BaseModel):
    id: uuid.UUID
    seq: int
    event_type: str
    occurred_at: datetime
    modalidad: str
    source: str
    travel_computes: bool
    geo: str | None
    prev_hash: str
    hash: str
    corrections: list[ExportCorrectionRow] = []


class ExportReport(BaseModel):
    worker_id: uuid.UUID
    employee_code: str
    full_name: str
    period: str
    start: datetime
    end: datetime
    efectivo_min: int
    ordinarias_min: int
    extra_min: int
    complementarias_min: int
    ordinary_min: int
    pausa_min: int = 0
    # Jornada flexible por trabajador (clave para la subvención, REQ-29).
    flexible_schedule: bool = False
    # Cómputo anual del tope de jornada del convenio (REQ-27).
    annual_worked_min: int = 0
    annual_cap_min: int = 0
    annual_remaining_min: int = 0
    # Saldo de vacaciones del año en curso (REQ-28).
    vacation_days_entitled: float = 0
    vacation_days_taken: int = 0
    vacation_days_remaining: float = 0
    # Ausencias del periodo (vacaciones/bajas/permisos). Sin binario del justificante.
    absences: list[ExportAbsenceRow] = []
    generated_at: datetime
    records: list[ExportRecordRow]
