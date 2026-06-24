"""Cifrado de geo y verificación de residencia/TLS (REQ-20, REQ-23). Unit, sin BD."""

from __future__ import annotations

import pytest

from app.core.config import Settings, db_uses_tls
from app.core.crypto import decrypt_geo, encrypt_geo


def test_encrypt_geo_round_trip():
    token = encrypt_geo("40.4168,-3.7038")
    assert token is not None
    # El ciphertext NO es el texto plano (cifrado en reposo).
    assert token != "40.4168,-3.7038"
    assert decrypt_geo(token) == "40.4168,-3.7038"


def test_encrypt_geo_none_and_empty():
    assert encrypt_geo(None) is None
    assert encrypt_geo("") is None
    assert decrypt_geo(None) is None
    assert decrypt_geo("") is None


def test_decrypt_invalid_token_is_tolerant():
    # Un token corrupto no revienta: devuelve None.
    assert decrypt_geo("not-a-valid-fernet-token") is None


def test_encrypt_geo_is_non_deterministic():
    # Fernet incluye IV/timestamp: dos cifrados del mismo valor difieren, pero descifran igual.
    a = encrypt_geo("1.0,2.0")
    b = encrypt_geo("1.0,2.0")
    assert a != b
    assert decrypt_geo(a) == decrypt_geo(b) == "1.0,2.0"


@pytest.mark.parametrize(
    "url,require,expected",
    [
        ("postgresql+asyncpg://u:p@h:5432/db?sslmode=require", True, True),
        ("postgresql+asyncpg://u:p@h:5432/db?ssl=require", True, True),
        ("postgresql+asyncpg://u:p@h:5432/db?ssl=true", True, True),
        ("postgresql+asyncpg://u:p@h:5432/db", True, False),
        ("postgresql+asyncpg://u:p@h:5432/db", False, True),  # dev: no se exige TLS
    ],
)
def test_db_uses_tls(url, require, expected):
    s = Settings(database_url=url, db_require_tls=require)
    assert db_uses_tls(s) is expected
