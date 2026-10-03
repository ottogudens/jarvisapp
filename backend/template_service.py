"""Procesamiento determinista de plantillas. Solo reemplaza campos {{nombre}}."""
import base64
import io
import re
import zipfile
from pathlib import Path

FIELD_RE = re.compile(r"\{\{\s*([a-zA-Z][a-zA-Z0-9_.-]{0,99})\s*\}\}")


def detect_fields(content: bytes, extension: str) -> list[str]:
    # La deteccion de OOXML se realiza sobre su XML interno; otros formatos son texto.
    if extension in {".docx", ".dotx", ".xlsx", ".xltx"}:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            text = "\n".join(archive.read(name).decode("utf-8", errors="ignore") for name in archive.namelist() if name.endswith(".xml"))
    else:
        text = content.decode("utf-8", errors="ignore")
    return sorted(set(FIELD_RE.findall(text)))


def _replace_text(value: str, fields: dict) -> str:
    return FIELD_RE.sub(lambda m: str(fields.get(m.group(1), m.group(0))), value)


def render_template(content: bytes, filename: str, fields: dict) -> tuple[bytes, str, str]:
    extension = Path(filename).suffix.lower()
    if extension in {".txt", ".md", ".html", ".csv"}:
        mime = {".txt": "text/plain", ".md": "text/markdown", ".html": "text/html", ".csv": "text/csv"}[extension]
        return _replace_text(content.decode("utf-8"), fields).encode("utf-8"), mime, filename
    if extension in {".docx", ".dotx"}:
        from docx import Document
        doc = Document(io.BytesIO(content))
        for paragraph in list(doc.paragraphs) + [p for table in doc.tables for row in table.rows for cell in row.cells for p in cell.paragraphs]:
            for run in paragraph.runs:
                run.text = _replace_text(run.text, fields)
        out = io.BytesIO(); doc.save(out)
        return out.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document", filename.rsplit('.', 1)[0] + '.docx'
    if extension in {".xlsx", ".xltx"}:
        from openpyxl import load_workbook
        book = load_workbook(io.BytesIO(content))
        for sheet in book.worksheets:
            for row in sheet.iter_rows():
                for cell in row:
                    if isinstance(cell.value, str): cell.value = _replace_text(cell.value, fields)
        out = io.BytesIO(); book.save(out)
        return out.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", filename.rsplit('.', 1)[0] + '.xlsx'
    if extension == ".pdf":
        from pypdf import PdfReader, PdfWriter
        reader = PdfReader(io.BytesIO(content)); writer = PdfWriter(); writer.clone_document_from_reader(reader)
        if not reader.get_fields(): raise ValueError("El PDF no contiene campos rellenables; úsalo como referencia para generar una plantilla DOCX o HTML.")
        for page in writer.pages: writer.update_page_form_field_values(page, fields)
        out = io.BytesIO(); writer.write(out)
        return out.getvalue(), "application/pdf", filename
    raise ValueError("Formato de plantilla no soportado.")
