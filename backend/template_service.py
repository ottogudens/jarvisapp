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


def convert_pdf_to_fillable(content: bytes, fields: list[dict]) -> tuple[bytes, list[str]]:
    """Crea un AcroForm sobre un PDF estático sin modificar su contenido base.

    Cada campo requiere name, page, x, y, width y height en puntos PDF (origen
    abajo-izquierda). La UI será responsable de capturar estas coordenadas.
    """
    from pypdf import PdfReader, PdfWriter
    from reportlab.pdfgen import canvas
    reader = PdfReader(io.BytesIO(content))
    if reader.get_fields():
        raise ValueError("El PDF ya contiene campos rellenables.")
    writer = PdfWriter()
    names = []
    by_page = {}
    for field in fields:
        try:
            name = str(field["name"])
            page = int(field["page"])
            x, y = float(field["x"]), float(field["y"])
            width, height = float(field["width"]), float(field["height"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Cada campo debe incluir name, page, x, y, width y height válidos.") from exc
        if not FIELD_RE.fullmatch("{{" + name + "}}") or page < 0 or page >= len(reader.pages) or min(width, height) <= 0:
            raise ValueError("Definición de campo inválida.")
        by_page.setdefault(page, []).append((name, x, y, width, height)); names.append(name)
    for number, background in enumerate(reader.pages):
        size = (float(background.mediabox.width), float(background.mediabox.height))
        layer = io.BytesIO(); canvas_obj = canvas.Canvas(layer, pagesize=size)
        for name, x, y, width, height in by_page.get(number, []):
            canvas_obj.acroform.textfield(name=name, x=x, y=y, width=width, height=height, borderWidth=1, forceBorder=True)
        canvas_obj.save(); layer.seek(0)
        form_page = PdfReader(layer).pages[0]
        form_page.merge_page(background)
        writer.add_page(form_page)
    writer.set_need_appearances_writer()
    out = io.BytesIO(); writer.write(out)
    return out.getvalue(), names
