"""Esquemas Pydantic v2 para los reportes de horas (REQ-08, REQ-12).

El reporte de horas extra totaliza el efectivo del periodo y lo reparte en ordinarias/extra.
La compensación (abono/descanso, art. 35 ET) se computa pero no se decide aquí: `pending`
hasta que la Fase 4 (correcciones versionadas) selle la decisión.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class OvertimeReport(BaseModel):
    worker_id: uuid.UUID
    period: Literal["daily", "weekly", "monthly"]
    start: datetime
    end: datetime
    efectivo_min: int
    ordinarias_min: int
    extra_min: int
    ordinary_min: int
    compensacion: str = "pending"
