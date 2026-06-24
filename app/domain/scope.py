"""Excepciones de ámbito de la obligación de registro de jornada (REQ-11). Lógica pura.

No todo trabajador genera para Global Meats la obligación de registrar su jornada (art. 34.9
ET / RDL 8/2019, según la relación laboral):

  - alta_direccion -> EXCLUIDO del registro obligatorio (relación laboral especial del
    art. 2.1.a ET): no se le exige fichar. El sistema puede registrar a título informativo,
    pero no lo trata como incumplimiento si no hay registros.
  - ett / subcontrata -> la obligación de registro recae en la EMPRESA USUARIA / principal,
    no en quien aquí gestiona la cuenta. `registration_obligor` devuelve la usuaria.
  - ordinaria / tiempo_parcial -> registro obligatorio normal (la usuaria es Global Meats).

Esto es clasificación de dominio: las decisiones de exposición (export/portal) la consultan
para no marcar como incumplimiento la ausencia de fichajes de un excluido.
"""

from __future__ import annotations

import uuid
from typing import Protocol

# Relaciones excluidas del deber de registro de jornada para esta empresa (REQ-11).
_EXCLUDED_FROM_RECORD = frozenset({"alta_direccion"})
# Relaciones cuya obligación de registro corresponde a la empresa usuaria/principal.
_USUARIA_OBLIGED = frozenset({"ett", "subcontrata"})


class _Worker(Protocol):
    id: uuid.UUID
    relation_type: str
    usuaria_id: uuid.UUID | None


def requires_time_record(worker: _Worker) -> bool:
    """¿Está este trabajador obligado a registrar jornada en este sistema? (REQ-11).

    False para alta dirección (excluida). True en el resto, aunque en ETT/subcontrata el
    obligado formal sea la usuaria (ver `registration_obligor`); aquí seguimos registrando.
    """
    return worker.relation_type not in _EXCLUDED_FROM_RECORD


def registration_obligor(worker: _Worker) -> uuid.UUID | None:
    """Quién es el obligado al registro: la empresa usuaria (ETT/subcontrata) o nosotros.

    Devuelve `usuaria_id` cuando la obligación se traslada a la usuaria/principal; en otro
    caso `None` (la obligación es de Global Meats, el responsable por defecto).
    """
    if worker.relation_type in _USUARIA_OBLIGED:
        return worker.usuaria_id
    return None
