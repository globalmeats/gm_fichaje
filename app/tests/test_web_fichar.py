"""Frontend SSR — pantalla de fichar (Fase 7, REQ-01). Requiere BD.

El estado lo reconstruye el backend; los botones reflejan las transiciones válidas y una
transición inválida devuelve el fragmento con el mensaje 409 legible (htmx swap).
"""

from __future__ import annotations

from app.core.security import create_access_token
from app.services.onboarding import create_employee
from app.web.session import COOKIE_NAME


async def _session(client, db, role: str = "empleado"):
    created = await create_employee(db, "Eva", "Mora", role=role)
    token = create_access_token(created.id, role, pin_temporary=False)
    client.cookies.set(COOKIE_NAME, token)
    return created


async def test_fichar_idle(client, db):
    await _session(client, db)
    r = await client.get("/fichar")
    assert r.status_code == 200
    assert "Sin jornada abierta" in r.text
    assert "Entrar" in r.text


async def test_check_in_opens_journey(client, db):
    await _session(client, db)
    r = await client.post("/fichar/evento", data={"event_type": "check_in"})
    assert r.status_code == 200
    assert "Jornada abierta" in r.text
    assert "Salir" in r.text


async def test_invalid_transition_shows_message(client, db):
    await _session(client, db)
    # check_out desde IDLE no es válido: fragmento con un aviso AMABLE, estado intacto.
    r = await client.post("/fichar/evento", data={"event_type": "check_out"})
    assert r.status_code == 200
    assert "no es válida en tu estado actual" in r.text
    assert "Sin jornada abierta" in r.text


async def test_desplazamiento_solo_si_habilitado(client, db):
    """Los botones de desplazamiento solo aparecen (y solo se aceptan) si el trabajador lo tiene."""
    import uuid as _uuid

    from app.db.models import Worker

    w = await _session(client, db)  # travel_enabled=False por defecto
    await client.post("/fichar/evento", data={"event_type": "check_in"})  # ABIERTA
    r = await client.get("/fichar")
    assert "Iniciar desplazamiento" not in r.text  # botón oculto
    # Guarda de servidor: aunque se fuerce el POST, se rechaza.
    r = await client.post("/fichar/evento", data={"event_type": "travel_start"})
    assert "no está habilitado" in r.text

    # Con el flag activado, sí aparece.
    worker = await db.get(Worker, _uuid.UUID(w.id))
    worker.travel_enabled = True
    await db.commit()
    r = await client.get("/fichar")
    assert "Iniciar desplazamiento" in r.text


async def test_modalidad_selector_y_registro(client, db):
    """El selector de modalidad aparece y el fichaje guarda la modalidad elegida."""
    import uuid as _uuid

    from sqlalchemy import select as _select

    from app.db.models import TimeRecord

    w = await _session(client, db)
    r = await client.get("/fichar")
    assert "Modalidad" in r.text and "A distancia" in r.text  # etiquetas visibles

    await client.post("/fichar/evento", data={"event_type": "check_in", "modalidad": "movil"})
    rec = (
        await db.execute(
            _select(TimeRecord).where(TimeRecord.worker_id == _uuid.UUID(w.id))
        )
    ).scalar_one()
    assert rec.modalidad == "movil"  # valor interno; se muestra como "A distancia"


async def test_full_sequence(client, db):
    await _session(client, db)
    r = await client.post("/fichar/evento", data={"event_type": "check_in"})
    assert "Jornada abierta" in r.text

    r = await client.post("/fichar/evento", data={"event_type": "break_start"})
    assert "En pausa" in r.text

    r = await client.post("/fichar/evento", data={"event_type": "break_end"})
    assert "Jornada abierta" in r.text

    r = await client.post("/fichar/evento", data={"event_type": "check_out"})
    assert "Sin jornada abierta" in r.text
