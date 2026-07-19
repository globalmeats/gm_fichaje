"""Bloque de hallazgos bajos de la auditoría: BUG-08, SEC-09, SEC-10, CMP-06."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.core.uploads import content_disposition, sniff_matches
from app.jobs.retention import RETENTION_YEARS, retention_cutoff
from app.schemas.fichaje import OfflineEventRequest

# ---- BUG-08: retención por años de calendario, no 365*4 ----


def test_retention_cutoff_uses_calendar_years():
    now = datetime(2026, 3, 1, 12, tzinfo=UTC)
    cutoff = retention_cutoff(now)
    assert cutoff == datetime(2026 - RETENTION_YEARS, 3, 1, 12, tzinfo=UTC)


def test_retention_cutoff_handles_leap_day():
    now = datetime(2028, 2, 29, 9, tzinfo=UTC)  # 2028 bisiesto; 2024 también
    assert retention_cutoff(now) == datetime(2024, 2, 29, 9, tzinfo=UTC)


# ---- SEC-10: bytes mágicos y Content-Disposition seguro ----


def test_sniff_matches_signatures():
    assert sniff_matches("application/pdf", b"%PDF-1.7 ...")
    assert sniff_matches("image/png", b"\x89PNG\r\n\x1a\n....")
    assert sniff_matches("image/jpeg", b"\xff\xd8\xff\xe0....")
    assert not sniff_matches("application/pdf", b"<html>nope")
    assert not sniff_matches("text/plain", b"whatever")


def test_content_disposition_sanitizes_filename():
    cd = content_disposition('ev"il\r\n; name.pdf')
    assert "\r" not in cd and "\n" not in cd
    assert '"ev' not in cd or '\\' not in cd  # sin comillas rotas
    assert "filename*=UTF-8''" in cd


# ---- CMP-06: client_event_id acotado (no puede inyectar el separador del sellado) ----


def test_client_event_id_rejects_separator():
    with pytest.raises(ValueError):
        OfflineEventRequest(
            event_type="check_in",
            occurred_at=datetime(2026, 7, 1, 8, tzinfo=UTC),
            client_event_id="abc|def",  # el '|' es el separador del payload sellado
        )


def test_client_event_id_accepts_uuid_like():
    ev = OfflineEventRequest(
        event_type="check_in",
        occurred_at=datetime(2026, 7, 1, 8, tzinfo=UTC),
        client_event_id="dev-1:2026-07-01T08:00:00",
    )
    assert ev.client_event_id


# ---- SEC-09: rechazo de Origin cruzado en métodos que mutan ----


async def test_cross_origin_post_rejected(client):
    r = await client.post(
        "/auth/login",
        json={"employee_code": "XxXx", "pin": "123456"},
        headers={"Origin": "https://evil.example", "Host": "testserver"},
    )
    assert r.status_code == 403
    assert "CSRF" in r.json()["detail"]
