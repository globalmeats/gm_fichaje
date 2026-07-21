"""REQ-16: las correcciones alimentan el cálculo de horas (overlay) + coherencia temporal.

Tests puros de dominio (sin BD): reproducen el caso real de producción (8h 32m → 11h 44m tras
corregir) y cubren "última gana", jornada incoherente = 0 y detección de discrepancias.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.domain.corrections import apply_corrections, discrepancies
from app.domain.hours import classify_overtime, journey_effective, reconstruct_journeys


class _Pol:
    pause_computable_default = True
    computation_period = "monthly"
    ordinary_hours_per_period = 160


def _rec(rid, seq, ev, iso, travel=True, modalidad="presencial"):
    return SimpleNamespace(
        id=rid, seq=seq, event_type=ev,
        occurred_at=datetime.fromisoformat(iso), travel_computes=travel, modalidad=modalidad,
    )


def _corr(rid, seq, field, value):
    return SimpleNamespace(original_record_id=rid, seq=seq, field=field, corrected_value=value)


def _min(td: timedelta) -> int:
    return int(td.total_seconds() // 60)


# Los 8 eventos reales de la trabajadora (en UTC).
_EVENTS = [
    _rec("r1", 1, "check_in", "2026-07-20T10:04:29+00:00"),
    _rec("r2", 2, "break_start", "2026-07-20T11:12:51+00:00"),
    _rec("r3", 3, "break_end", "2026-07-21T06:09:30+00:00"),
    _rec("r4", 4, "check_out", "2026-07-21T06:09:39+00:00"),
    _rec("r5", 5, "check_in", "2026-07-21T06:09:41+00:00"),
    _rec("r6", 6, "break_start", "2026-07-21T11:08:19+00:00"),
    _rec("r7", 7, "break_end", "2026-07-21T13:34:14+00:00"),
    _rec("r8", 8, "check_out", "2026-07-21T15:59:15+00:00"),
]
_NOW = datetime(2026, 7, 25, tzinfo=UTC)  # dentro del periodo (julio 2026)


def test_caso_real_sin_correcciones_da_8h32m():
    out = classify_overtime(apply_corrections(_EVENTS, []), _Pol(), _NOW)
    assert _min(out["efectivo"]) == 512  # 8h 32m (jornada del 20 destrozada por la pausa nocturna)


def test_caso_real_con_correcciones_da_11h44m():
    # Corrige break_end y check_out del 20 (lo que hizo el admin en prod).
    corrs = [
        _corr("r3", 1, "occurred_at", "2026-07-20T12:15:00.000Z"),
        _corr("r4", 2, "occurred_at", "2026-07-20T15:27:00.000Z"),
    ]
    out = classify_overtime(apply_corrections(_EVENTS, corrs), _Pol(), _NOW)
    assert _min(out["efectivo"]) == 704  # 11h 44m (jornada del 20 ya sana: ~4h20m + ~7h24m)


def test_ultima_correccion_gana():
    records = [_rec("r1", 1, "check_in", "2026-07-20T10:00:00+00:00")]
    corrs = [
        _corr("r1", 1, "occurred_at", "2026-07-20T11:00:00Z"),
        _corr("r1", 2, "occurred_at", "2026-07-20T12:00:00Z"),
    ]
    eff = apply_corrections(records, corrs)
    assert eff[0].occurred_at == datetime.fromisoformat("2026-07-20T12:00:00+00:00")


def test_jornada_incoherente_computa_cero_y_se_detecta():
    # check_out antes de check_in (p. ej. corrección a medias).
    records = [
        _rec("a", 1, "check_in", "2026-07-20T10:00:00+00:00"),
        _rec("b", 2, "check_out", "2026-07-20T08:00:00+00:00"),
    ]
    eff = apply_corrections(records, [])
    journey = reconstruct_journeys(eff)[0]
    assert journey_effective(journey, _Pol()) == timedelta(0)
    d = discrepancies(eff)
    assert d and "anterior a la entrada" in d[0]


def test_correccion_event_type_afecta_calculo():
    # Corregir un break_start a check_out cierra la jornada antes: cambia el efectivo.
    records = [
        _rec("r1", 1, "check_in", "2026-07-20T08:00:00+00:00"),
        _rec("r2", 2, "break_start", "2026-07-20T12:00:00+00:00"),
    ]
    corrs = [_corr("r2", 1, "event_type", "check_out")]
    out = classify_overtime(apply_corrections(records, corrs), _Pol(), _NOW)
    assert _min(out["efectivo"]) == 240  # 4h (08:00→12:00 cerrada), no jornada abierta (0)
