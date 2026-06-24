"""Cifrado en reposo de columnas sensibles (REQ-20, REQ-23).

La coordenada de geolocalización (`time_record.geo`) es un dato personal que solo se capta
con consentimiento y solo en el instante del fichaje (skill rgpd-dataguard §4). Aquí se cifra
en la capa de aplicación con Fernet (AES-128-CBC + HMAC, autenticado): la clave vive en
`settings.geo_encryption_key` (variable de entorno), NUNCA en la base de datos, de modo que un
volcado del Postgres no expone las coordenadas. El sellado de `time_record` encadena el
*ciphertext* almacenado; como Fernet es autenticado, manipularlo rompe el hash y no se puede
forjar.
"""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


def _fernet() -> Fernet:
    """Deriva una clave Fernet (32 bytes url-safe base64) de `settings.geo_encryption_key`.

    Aceptamos cualquier secreto de configuración y lo normalizamos a una clave válida con
    SHA-256, así el operador no tiene que generar un base64 de 32 bytes a mano.
    """
    digest = hashlib.sha256(settings.geo_encryption_key.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_geo(plaintext: str | None) -> str | None:
    """Cifra una coordenada. `None`/vacío -> `None` (no se almacena nada)."""
    if not plaintext:
        return None
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt_geo(token: str | None) -> str | None:
    """Descifra una coordenada. Tolerante: `None` o token inválido -> `None`."""
    if not token:
        return None
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        return None
