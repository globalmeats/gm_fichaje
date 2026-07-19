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

# SEC-08: geolocalización y justificantes médicos se cifran con claves DISTINTAS, para que el
# compromiso de una no exponga la otra categoría de dato. Se derivan de sus secretos de entorno
# con SHA-256 + separación de dominio; el secreto debe ser aleatorio de alta entropía (ver
# docs/BACKUP.md y .env.example). Si `doc_encryption_key` no está configurada, la clave de
# documentos se deriva del secreto de geo con una etiqueta distinta (siguen siendo claves
# diferentes); en producción conviene una `DOC_ENCRYPTION_KEY` dedicada.


def _derive_fernet(secret: str, label: str) -> Fernet:
    digest = hashlib.sha256(f"{label}:{secret}".encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _fernet_for(kind: str) -> Fernet:
    if kind == "geo":
        return _derive_fernet(settings.geo_encryption_key, "geo")
    # documentos: clave dedicada si existe; si no, derivada del secreto de geo con otra etiqueta.
    secret = settings.doc_encryption_key or settings.geo_encryption_key
    return _derive_fernet(secret, "doc")


def encrypt_geo(plaintext: str | None) -> str | None:
    """Cifra una coordenada. `None`/vacío -> `None` (no se almacena nada)."""
    if not plaintext:
        return None
    return _fernet_for("geo").encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt_geo(token: str | None) -> str | None:
    """Descifra una coordenada. Tolerante: `None` o token inválido -> `None`."""
    if not token:
        return None
    try:
        return _fernet_for("geo").decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        return None


def encrypt_blob(data: bytes) -> bytes:
    """Cifra un binario (justificante de asistencia, REQ-28) con la clave de documentos.

    El documento se guarda CIFRADO en `absence_document.content_encrypted`: un volcado del
    Postgres no expone el adjunto, y la clave vive solo en el entorno.
    """
    return _fernet_for("doc").encrypt(data)


def decrypt_blob(token: bytes) -> bytes:
    """Descifra un binario cifrado con `encrypt_blob`. Lanza si el token es inválido."""
    return _fernet_for("doc").decrypt(token)
