"""Pausas, desplazamientos y resumen de tiempo efectivo (REQ-07, REQ-09). Requiere BD.

Flujo de los 6 eventos, rechazo de transiciones imposibles (409), y `GET /fichaje/summary`
con aislamiento por trabajador.
"""

from __future__ import annotations

from app.core.security import create_access_token
from app.services.onboarding import create_employee


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _post(client, h, event_type, **extra):
    return await client.post(
        "/fichaje/event", json={"event_type": event_type, **extra}, headers=h
    )


async def test_break_flow_states(client, db):
    w = await create_employee(db, "Pau", "Sas")
    h = _auth(create_access_token(w.id, "empleado", pin_temporary=False))

    assert (await _post(client, h, "check_in")).status_code == 201
    assert (await _post(client, h, "break_start")).status_code == 201

    r = await client.get("/fichaje/today", headers=h)
    assert r.json()["state"] == "EN_PAUSA"

    assert (await _post(client, h, "break_end")).status_code == 201
    r = await client.get("/fichaje/today", headers=h)
    assert r.json()["state"] == "ABIERTA"

    assert (await _post(client, h, "check_out")).status_code == 201
    r = await client.get("/fichaje/today", headers=h)
    assert r.json()["state"] == "IDLE"


async def test_break_end_without_start_conflict(client, db):
    w = await create_employee(db, "Mal", "Pausa")
    h = _auth(create_access_token(w.id, "empleado", pin_temporary=False))

    assert (await _post(client, h, "check_in")).status_code == 201
    # break_end sin break_start no es transición válida desde ABIERTA.
    assert (await _post(client, h, "break_end")).status_code == 409


async def test_travel_flow(client, db):
    w = await create_employee(db, "Via", "Jero")
    h = _auth(create_access_token(w.id, "empleado", pin_temporary=False))

    assert (await _post(client, h, "check_in")).status_code == 201
    r = await _post(client, h, "travel_start", travel_computes=False)
    assert r.status_code == 201
    r = await client.get("/fichaje/today", headers=h)
    assert r.json()["state"] == "EN_DESPLAZAMIENTO"

    assert (await _post(client, h, "travel_end")).status_code == 201
    assert (await _post(client, h, "check_out")).status_code == 201


async def test_summary_reflects_journey(client, db):
    w = await create_employee(db, "Sum", "Mary")
    h = _auth(create_access_token(w.id, "empleado", pin_temporary=False))

    await _post(client, h, "check_in")
    await _post(client, h, "check_out")

    r = await client.get("/fichaje/summary", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["today"]) == 1
    assert body["today"][0]["open"] is False
    assert body["today"][0]["efectivo_min"] >= 0
    assert body["period"]["period"] in ("daily", "weekly", "monthly")


async def test_summary_isolation_between_workers(client, db):
    w1 = await create_employee(db, "Aaa", "Uno")
    w2 = await create_employee(db, "Bbb", "Dos")
    h1 = _auth(create_access_token(w1.id, "empleado", pin_temporary=False))
    h2 = _auth(create_access_token(w2.id, "empleado", pin_temporary=False))

    await _post(client, h1, "check_in")
    await _post(client, h1, "check_out")

    # w2 no tiene jornadas: su summary está vacío.
    r = await client.get("/fichaje/summary", headers=h2)
    assert r.json()["today"] == []
