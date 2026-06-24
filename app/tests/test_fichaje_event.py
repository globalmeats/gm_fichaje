"""Fichaje extremo a extremo (REQ-01, REQ-15). Requiere BD.

check_in/check_out, reconstrucción de estado, rechazo de transiciones imposibles (409),
PIN temporal bloqueado (403), encadenado de hash y aislamiento por trabajador.
"""

from __future__ import annotations

from app.core.security import create_access_token
from app.services.onboarding import create_employee


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_pin_temporary_blocked(client, db):
    w = await create_employee(db, "Pepe", "Garcia")
    token = create_access_token(w.id, "empleado", pin_temporary=True)
    r = await client.post(
        "/fichaje/event", json={"event_type": "check_in"}, headers=_auth(token)
    )
    assert r.status_code == 403


async def test_check_in_out_flow_and_chain(client, db):
    w = await create_employee(db, "Ana", "Gil")
    h = _auth(create_access_token(w.id, "empleado", pin_temporary=False))

    # check_in -> 201, primer eslabón GENESIS.
    r = await client.post("/fichaje/event", json={"event_type": "check_in"}, headers=h)
    assert r.status_code == 201, r.text
    first = r.json()
    assert first["seq"] == 1
    assert first["prev_hash"] == "GENESIS"

    # /today refleja ABIERTA y un evento.
    r = await client.get("/fichaje/today", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["state"] == "ABIERTA"
    assert len(body["events"]) == 1

    # check_out -> 201, encadena con el hash anterior, seq incrementa.
    r = await client.post("/fichaje/event", json={"event_type": "check_out"}, headers=h)
    assert r.status_code == 201
    second = r.json()
    assert second["seq"] == 2
    assert second["prev_hash"] == first["hash"]

    # Vuelve a IDLE.
    r = await client.get("/fichaje/today", headers=h)
    assert r.json()["state"] == "IDLE"


async def test_double_check_in_conflict(client, db):
    w = await create_employee(db, "Leo", "Diaz")
    h = _auth(create_access_token(w.id, "empleado", pin_temporary=False))

    r = await client.post("/fichaje/event", json={"event_type": "check_in"}, headers=h)
    assert r.status_code == 201
    r = await client.post("/fichaje/event", json={"event_type": "check_in"}, headers=h)
    assert r.status_code == 409


async def test_check_out_without_check_in_conflict(client, db):
    w = await create_employee(db, "Mia", "Roca")
    h = _auth(create_access_token(w.id, "empleado", pin_temporary=False))

    r = await client.post("/fichaje/event", json={"event_type": "check_out"}, headers=h)
    assert r.status_code == 409


async def test_isolation_between_workers(client, db):
    w1 = await create_employee(db, "Uno", "Alfa")
    w2 = await create_employee(db, "Dos", "Beta")
    h1 = _auth(create_access_token(w1.id, "empleado", pin_temporary=False))
    h2 = _auth(create_access_token(w2.id, "empleado", pin_temporary=False))

    await client.post("/fichaje/event", json={"event_type": "check_in"}, headers=h1)

    # w2 no ve nada de w1: su cadena es independiente.
    r = await client.get("/fichaje/today", headers=h2)
    body = r.json()
    assert body["state"] == "IDLE"
    assert body["events"] == []

    # w2 ficha y su primer eslabón también es GENESIS (cadena propia).
    r = await client.post("/fichaje/event", json={"event_type": "check_in"}, headers=h2)
    assert r.json()["prev_hash"] == "GENESIS"
