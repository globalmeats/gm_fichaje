"""Aplicación de correcciones al cálculo de horas (REQ-16). Lógica pura, sin BD.

Los `time_record` son inmutables; una corrección es una fila append-only en `record_correction`
que rectifica un campo. Hasta la auditoría 2026-07 las correcciones eran solo de auditoría (se
mostraban pero no afectaban a los totales). Aquí se construye la vista EFECTIVA de cada registro
—con la ÚLTIMA corrección de cada campo superpuesta— que alimenta el cómputo de tiempo efectivo.
El registro original permanece sellado; solo se superpone para calcular y para detectar
incoherencias temporales (que se señalan por banner y bloquean el sellado sin confirmación).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.core.time import to_madrid
from app.domain.hours import Journey, journey_coherent, reconstruct_journeys

# Campos corregibles que afectan al CÓMPUTO de horas (geo no interviene en el cálculo).
_HOUR_FIELDS = ("occurred_at", "event_type", "travel_computes", "modalidad")


@dataclass
class EffectiveRecord:
    """Registro con sus correcciones aplicadas, para reconstruir jornadas (duck-typed _Record)."""

    seq: int
    event_type: str
    occurred_at: datetime
    travel_computes: bool
    modalidad: str


def _parse_dt(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


def apply_corrections(records: list, corrections: list) -> list[EffectiveRecord]:
    """Superpone la última corrección (por `seq`) de cada campo sobre cada registro.

    `records`: `time_record` originales. `corrections`: `record_correction` del trabajador.
    Devuelve las vistas efectivas en orden de `seq` (la secuencia lógica no cambia; solo los
    valores). El orden por `seq` se mantiene aunque una corrección de hora vaya "hacia atrás".
    """
    latest: dict[tuple, object] = {}
    for c in corrections:
        if c.field not in _HOUR_FIELDS:
            continue  # geo no afecta al cálculo
        key = (c.original_record_id, c.field)
        prev = latest.get(key)
        if prev is None or c.seq > prev.seq:
            latest[key] = c

    out: list[EffectiveRecord] = []
    for r in records:
        event_type = r.event_type
        occurred_at = r.occurred_at
        travel_computes = r.travel_computes
        modalidad = r.modalidad
        if (c := latest.get((r.id, "event_type"))) is not None:
            event_type = c.corrected_value
        if (c := latest.get((r.id, "occurred_at"))) is not None:
            occurred_at = _parse_dt(c.corrected_value)
        if (c := latest.get((r.id, "travel_computes"))) is not None:
            travel_computes = c.corrected_value.lower() == "true"
        if (c := latest.get((r.id, "modalidad"))) is not None:
            modalidad = c.corrected_value
        out.append(
            EffectiveRecord(
                seq=r.seq,
                event_type=event_type,
                occurred_at=occurred_at,
                travel_computes=travel_computes,
                modalidad=modalidad,
            )
        )
    out.sort(key=lambda e: e.seq)
    return out


def _hm(dt: datetime) -> str:
    return to_madrid(dt).strftime("%H:%M")


def _describe(journey: Journey) -> list[str]:
    day = to_madrid(journey.check_in).strftime("%d/%m/%Y")
    msgs: list[str] = []
    if journey.check_out is not None and journey.check_out < journey.check_in:
        msgs.append(
            f"Jornada del {day}: la salida ({_hm(journey.check_out)}) es anterior a la "
            f"entrada ({_hm(journey.check_in)})."
        )
    for start, end in journey.pauses:
        if end < start:
            msgs.append(
                f"Jornada del {day}: una pausa termina ({_hm(end)}) antes de empezar "
                f"({_hm(start)})."
            )
    for start, end, _ in journey.travels:
        if end < start:
            msgs.append(
                f"Jornada del {day}: un desplazamiento termina ({_hm(end)}) antes de empezar "
                f"({_hm(start)})."
            )
    return msgs


def discrepancies(effective_records: list) -> list[str]:
    """Describe (legible) las incoherencias temporales de las jornadas efectivas, para el banner
    y para avisar antes de sellar una corrección que dejaría el histórico incoherente."""
    msgs: list[str] = []
    for journey in reconstruct_journeys(effective_records):
        if not journey_coherent(journey):
            msgs.extend(_describe(journey))
    return msgs
