"""Frontend SSR — correcciones, horas extra y desglose de tiempo efectivo (Fase 7).

Conecta a la UI lo que ya existía en el backend: crear correcciones versionadas (REQ-16),
el informe de horas extra por trabajador (REQ-08/12) y el desglose de jornada (REQ-07/09).
La seguridad real la imponen API+RLS; aquí el rol solo decide qué se muestra.
"""

from __future__ import annotations

from app.audit.chain import append_event
from app.core.security import create_access_token
from app.services.onboarding import create_employee
from app.web.session import COOKIE_NAME


async def _session(client, db, role: str):
    created = await create_employee(db, "Iris", "Sanz", role=role)
    token = create_access_token(created.id, role, pin_temporary=False)
    client.cookies.set(COOKIE_NAME, token)
    return created


async def test_empleado_forbidden_in_registros(client, db):
    await _session(client, db, "empleado")
    r = await client.get("/admin/registros", follow_redirects=False)
    assert r.status_code == 403


async def test_admin_registros_offers_correction(client, db):
    await _session(client, db, "admin")
    target = await create_employee(db, "Hugo", "Mas", role="empleado")
    await append_event(db, target.id, "check_in", modalidad="presencial", source="web")

    r = await client.get(
        f"/admin/registros?worker_id={target.id}&start=2020-01-01&end=2035-12-31"
    )
    assert r.status_code == 200
    assert "Corregir" in r.text


async def test_admin_registros_sin_fechas_avisa(client, db):
    """Sin fechas seleccionadas, muestra un banner amable (no un 422 JSON)."""
    await _session(client, db, "admin")
    target = await create_employee(db, "Sara", "Diaz", role="empleado")
    r = await client.get(f"/admin/registros?worker_id={target.id}")
    assert r.status_code == 200
    assert "Selecciona las fechas" in r.text


async def test_admin_creates_correction(client, db):
    await _session(client, db, "admin")
    target = await create_employee(db, "Lía", "Gil", role="empleado")
    rec = await append_event(db, target.id, "check_in", modalidad="presencial", source="web")

    r = await client.post(
        "/admin/correccion",
        data={
            "record_id": str(rec.id),
            "worker_id": str(target.id),
            "field": "modalidad",
            "corrected_value": "teletrabajo",
            "reason": "Error de selección",
        },
    )
    assert r.status_code == 200
    assert "Corrección registrada" in r.text
    # El original se muestra junto a su corrección (audit-trail §3).
    assert "teletrabajo" in r.text
    assert "Error de selección" in r.text


async def test_correccion_incoherente_avisa_y_confirma(client, db):
    """Corregir el check_out a antes del check_in avisa antes de sellar; con confirm se sella
    y queda el banner de discrepancia (REQ-16)."""
    await _session(client, db, "admin")
    target = await create_employee(db, "Eva", "Roca", role="empleado")
    await append_event(db, target.id, "check_in")  # ~ahora
    co = await append_event(db, target.id, "check_out")  # ~ahora + un instante

    # Mover el check_out a mucho antes del check_in → incoherencia.
    payload = {
        "record_id": str(co.id),
        "worker_id": str(target.id),
        "field": "occurred_at",
        "corrected_value": "2020-01-01T00:00:00.000Z",
        "reason": "prueba incoherencia",
    }
    r = await client.post("/admin/correccion", data=payload)
    assert r.status_code == 200
    assert "incoherencia" in r.text.lower()
    assert "Proceder de todos modos" in r.text
    assert "Corrección registrada" not in r.text  # NO se ha sellado

    # Confirmar: se sella y aparece el banner persistente de discrepancia.
    r2 = await client.post("/admin/correccion", data={**payload, "confirm": "true"})
    assert r2.status_code == 200
    assert "Corrección registrada" in r2.text
    assert "Discrepancia temporal" in r2.text
    # La anotación muestra la hora LOCAL del valor corregido (01/01/2020 01:00 Madrid = UTC+1).
    assert "hora local" in r2.text
    assert "01/01/2020 01:00:00" in r2.text


async def test_correction_invalid_value_shows_error(client, db):
    await _session(client, db, "admin")
    target = await create_employee(db, "Noa", "Rey", role="empleado")
    rec = await append_event(db, target.id, "check_in", modalidad="presencial", source="web")

    r = await client.post(
        "/admin/correccion",
        data={
            "record_id": str(rec.id),
            "worker_id": str(target.id),
            "field": "modalidad",
            "corrected_value": "no_existe",
            "reason": "x",
        },
    )
    assert r.status_code == 200
    assert "modalidad" in r.text.lower()


async def test_oversight_can_open_horas(client, db):
    await _session(client, db, "supervisor")
    r = await client.get("/admin/horas")
    assert r.status_code == 200
    assert "Horas extra" in r.text


async def test_journey_breakdown_on_fichar(client, db):
    worker = await _session(client, db, "empleado")
    await append_event(db, worker.id, "check_in", modalidad="presencial", source="web")
    r = await client.get("/fichar")
    assert r.status_code == 200
    assert "Tiempo efectivo de hoy" in r.text
