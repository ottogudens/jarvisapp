"""Validación centralizada de adjuntos no confiables."""

from pathlib import Path
import io
import zipfile

from fastapi import HTTPException

MAX_UPLOAD_BYTES = 15 * 1024 * 1024
MAX_UPLOAD_FILES = 5
ALLOWED_SUFFIXES = {".pdf", ".txt", ".md", ".csv", ".docx", ".xlsx", ".png", ".jpg", ".jpeg", ".webp", ".m4a", ".mp3", ".ogg", ".wav", ".webm"}
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
    # Office Open XML es un ZIP. Esta comprobación básica evita aceptar bytes
    # arbitrarios disfrazados de Word o Excel; los parsers validan lo restante.
    if suffix in {".docx", ".xlsx"} and not content.startswith(b"PK\x03\x04"):
        raise HTTPException(status_code=400, detail="El archivo Office no contiene una estructura válida.")
    if suffix in {".docx", ".xlsx"}:
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                entries = archive.infolist()
                expanded_size = sum(entry.file_size for entry in entries)
                expected = "word/document.xml" if suffix == ".docx" else "xl/workbook.xml"
                if expected not in archive.namelist() or len(entries) > 10_000 or expanded_size > 60 * 1024 * 1024:
                    raise HTTPException(status_code=400, detail="El archivo Office no cumple los límites de seguridad.")
        except zipfile.BadZipFile as exc:
            raise HTTPException(status_code=400, detail="El archivo Office está dañado.") from exc
    return safe_name
