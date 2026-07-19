"""Desconexión digital y desglose de horas complementarias (REQ-26).

Unit: `is_off_hours` (ventana, cruce de medianoche) y `classify_overtime` para tiempo parcial.
BD: un fichaje fuera de la ventana de desconexión genera una alerta `off_hours`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, time

from sqlalchemy import select

from app.core.security import create_access_token
from app.db.models import AuditAlert
from app.domain.desconexion import is_off_hours
from app.domain.hours import classify_overtime
from app.services.onboarding import create_employee


@dataclass
class _Rec:
    event_type: str
    occurred_at: datetime
    travel_computes: bool = True


@dataclass
class _Policy:
    pause_computable_default: bool = True
    computation_period: str = "monthly"
    ordinary_hours_per_period: float = 160
    desconexion_start: time | None = None
    desconexion_end: time | None = None


def _at(h: int, m: int = 0) -> datetime:
    return datetime(2026, 6, 24, h, m, tzinfo=UTC)


def _minutes(td) -> int:
    return int(td.total_seconds() // 60)


# ---- is_off_hours (unit) ----

def test_off_hours_false_when_no_window():
    assert is_off_hours(_at(3), _Policy()) is False


def test_off_hours_within_normal_window():
    # Ventana 08:00–20:00 en hora de Madrid (BUG-03: la comparación es local, no UTC).
    p = _Policy(desconexion_start=time(8), desconexion_end=time(20))
    assert is_off_hours(_at(10), p) is False  # 12:00 Madrid, dentro de la jornada
    assert is_off_hours(_at(22), p) is True   # 00:00 Madrid, de noche, fuera
    assert is_off_hours(_at(3), p) is True    # 05:00 Madrid, de madrugada, fuera


def test_off_hours_window_crossing_midnight():
    # Ventana de trabajo nocturna 22:00..06:00.
    p = _Policy(desconexion_start=time(22), desconexion_end=time(6))
    assert is_off_hours(_at(23), p) is False  # dentro (noche)
    assert is_off_hours(_at(2), p) is False   # dentro (madrugada)
    assert is_off_hours(_at(12), p) is True   # mediodía, fuera


# ---- classify_overtime: complementarias (unit) ----

def test_tiempo_parcial_excess_is_complementarias():
    recs = [_Rec("check_in", _at(9)), _Rec("check_out", _at(17))]  # 8h efectivo
    policy = _Policy(ordinary_hours_per_period=4)  # jornada parcial: 4h
    out = classify_overtime(recs, policy, _at(20), relation_type="tiempo_parcial")
    assert _minutes(out["ordinarias"]) == 4 * 60
    assert _minutes(out["complementarias"]) == 4 * 60
    assert _minutes(out["extra"]) == 0


def test_ordinaria_excess_is_extra_not_complementarias():
    recs = [_Rec("check_in", _at(9)), _Rec("check_out", _at(17))]  # 8h efectivo
    policy = _Policy(ordinary_hours_per_period=4)
    out = classify_overtime(recs, policy, _at(20), relation_type="ordinaria")
    assert _minutes(out["extra"]) == 4 * 60
    assert _minutes(out["complementarias"]) == 0


# ---- off_hours alert (BD) ----

async def _set_window(db, start: time, end: time) -> None:
    from app.db.models import TimePolicy

    policy = await db.get(TimePolicy, 1)
    policy.desconexion_start = start
    policy.desconexion_end = end
    await db.commit()


async def test_off_hours_event_generates_alert(client, db):
    # Ventana laboral de 1 minuto al inicio del día: salvo en ese minuto, todo es off-hours.
    now_t = datetime.now(UTC).time()
    assert not (time(0, 0) <= now_t < time(0, 1)), "test corrido en el minuto 00:00 (reintentar)"
    await _set_window(db, time(0, 0), time(0, 1))

    w = await create_employee(db, "Noc", "Turno")
    h = {"Authorization": f"Bearer {create_access_token(w.id, 'empleado', pin_temporary=False)}"}
    r = await client.post("/fichaje/event", json={"event_type": "check_in"}, headers=h)
    assert r.status_code == 201, r.text

    alerts = (
        await db.execute(
            select(AuditAlert).where(
                AuditAlert.worker_id == w.id, AuditAlert.alert_type == "off_hours"
            )
        )
    ).scalars().all()
    assert len(alerts) == 1
    assert alerts[0].severity == "info"
