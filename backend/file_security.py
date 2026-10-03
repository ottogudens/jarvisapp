"""Validación centralizada de adjuntos no confiables."""

from pathlib import Path

from fastapi import HTTPException

MAX_UPLOAD_BYTES = 15 * 1024 * 1024
MAX_UPLOAD_FILES = 5
ALLOWED_SUFFIXES = {".pdf", ".txt", ".md", ".csv", ".png", ".jpg", ".jpeg", ".webp", ".m4a", ".mp3", ".ogg", ".wav", ".webm"}
TEMPLATE_SUFFIXES = {".docx", ".dotx", ".xlsx", ".xltx", ".pdf", ".csv", ".html", ".txt", ".md"}


def validate_upload(filename: str | None, content_type: str | None, content: bytes) -> str:
    """Valida límites y firmas simples; devuelve un nombre seguro para persistir."""
    safe_name = Path(filename or "adjunto").name.strip()
    suffix = Path(safe_name).suffix.lower()
    if not safe_name or safe_name in {".", ".."} or suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=400, detail="Tipo de archivo no permitido.")
    if not content:
        raise HTTPException(status_code=400, detail=f"El archivo {safe_name} está vacío.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"El archivo {safe_name} excede el límite de 15 MB.")
    if len(safe_name) > 180:
        raise HTTPException(status_code=400, detail="El nombre del archivo es demasiado largo.")

    # La extensión o Content-Type no bastan. Estas comprobaciones son una primera
    # barrera; los analizadores (PyMuPDF/imagen/audio) siguen siendo necesarios.
    if suffix == ".pdf" and not content.startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="El archivo no contiene un PDF válido.")
    if suffix == ".png" and not content.startswith(b"\x89PNG\r\n\x1a\n"):
        raise HTTPException(status_code=400, detail="El archivo no contiene un PNG válido.")
    if suffix in {".jpg", ".jpeg"} and not content.startswith(b"\xff\xd8\xff"):
        raise HTTPException(status_code=400, detail="El archivo no contiene un JPEG válido.")
    if suffix == ".webp" and content[:4] != b"RIFF":
        raise HTTPException(status_code=400, detail="El archivo no contiene un WebP válido.")
    return safe_name
