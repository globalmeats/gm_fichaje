"""Logging de seguridad R3: eventos correctos, sin contenido sensible (PIN) en el log."""

from __future__ import annotations

import logging

import pytest

from app.core.config import settings
from app.core.logging import _JsonFormatter, client_ip, log_event
from app.services.onboarding import create_employee

LOGGER = "gm.security"


@pytest.fixture
def logs(caplog):
    caplog.set_level(logging.INFO, logger=LOGGER)
    return caplog


def _events(caplog, name: str) -> list[dict]:
    return [
        getattr(r, "fields", {}) for r in caplog.records if r.getMessage() == name
    ]


async def test_login_failed_and_ok_logged(client, db, logs):
    created = await create_employee(db, "Log", "Uno")

    r = await client.post("/login", data={"employee_code": created.employee_code, "pin": "000000"})
    assert r.status_code == 401
    failed = _events(logs, "login_failed")
    assert failed and failed[-1]["reason"] == "bad_pin"
    assert failed[-1]["code"] == created.employee_code

    r = await client.post(
        "/login", data={"employee_code": created.employee_code, "pin": created.pin}
    )
    assert r.status_code == 303
    ok = _events(logs, "login_ok")
    assert ok and ok[-1]["code"] == created.employee_code

    # El PIN jamás aparece en ningún registro del log.
    for record in logs.records:
        line = _JsonFormatter().format(record)
        assert created.pin not in line
        assert "000000" not in line


async def test_unknown_code_logged_without_leaking(client, logs):
    r = await client.post("/login", data={"employee_code": "NoExiste", "pin": "123456"})
    assert r.status_code == 401
    failed = _events(logs, "login_failed")
    assert failed and failed[-1]["reason"] == "unknown_or_inactive"
    # Respuesta uniforme: el log tampoco confirma existencia con un código.
    assert "code" not in failed[-1]


async def test_lockout_logged(client, db, logs):
    created = await create_employee(db, "Log", "Dos")
    for _ in range(settings.max_failed_attempts):
        await client.post(
            "/login", data={"employee_code": created.employee_code, "pin": "999999"}
        )
    locked = _events(logs, "account_locked")
    assert locked and locked[-1]["code"] == created.employee_code

    await client.post(
        "/login", data={"employee_code": created.employee_code, "pin": created.pin}
    )
    assert _events(logs, "login_locked_attempt")


def test_client_ip_ignores_cf_header_by_default(monkeypatch):
    class FakeClient:
        host = "10.0.0.9"

    class FakeRequest:
        headers = {"cf-connecting-ip": "1.2.3.4"}
        client = FakeClient()

    assert client_ip(FakeRequest()) == "10.0.0.9"
    monkeypatch.setattr(settings, "trust_cf_connecting_ip", True)
    assert client_ip(FakeRequest()) == "1.2.3.4"


def test_log_event_drops_none_fields(logs):
    log_event("export", format="csv", start=None)
    fields = _events(logs, "export")[-1]
    assert fields == {"format": "csv"}
