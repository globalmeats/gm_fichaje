"""Utilidades de subida/descarga de ficheros (SEC-10): validación de tipo real y cabecera segura.

El justificante (REQ-28) llega con un `content_type` declarado por el cliente; aquí se
comprueba contra los BYTES MÁGICOS reales para que un fichero no sea otra cosa disfrazada, y
se construye un `Content-Disposition` a prueba de inyección (RFC 6266) a partir del nombre.
"""

from __future__ import annotations

# Firmas de los tipos admitidos (PDF/JPEG/PNG). El content_type declarado debe coincidir.
_MAGIC: dict[str, tuple[bytes, ...]] = {
    "application/pdf": (b"%PDF",),
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
}


def sniff_matches(content_type: str, data: bytes) -> bool:
    """True si `data` empieza por una firma coherente con `content_type`."""
    signatures = _MAGIC.get(content_type)
    if not signatures:
        return False
    return any(data.startswith(sig) for sig in signatures)


def _ascii_fallback(filename: str) -> str:
    """Nombre ASCII sin comillas, saltos de línea ni separadores de cabecera."""
    safe = "".join(c for c in filename if 32 <= ord(c) < 127 and c not in '"\\')
    safe = safe.replace("\r", "").replace("\n", "").strip()
    return safe or "justificante"


def content_disposition(filename: str) -> str:
    """`Content-Disposition: attachment` seguro con nombre ASCII + `filename*` UTF-8 (RFC 6266)."""
    from urllib.parse import quote

    ascii_name = _ascii_fallback(filename)
    utf8_name = quote(filename, safe="")
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{utf8_name}"
