"""Esquemas Pydantic v2 para la política de tiempo (REQ-13, REQ-12).

`time_policy` es config de convenio ajustable sin tocar código: solo admin la edita.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TimePolicyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    pause_computable_default: bool
    computation_period: Literal["daily", "weekly", "monthly"]
    ordinary_hours_per_period: float
    updated_at: datetime


class TimePolicyUpdate(BaseModel):
    """Actualización parcial: solo se aplican los campos presentes."""

    pause_computable_default: bool | None = None
    computation_period: Literal["daily", "weekly", "monthly"] | None = None
    ordinary_hours_per_period: float | None = Field(default=None, gt=0)
