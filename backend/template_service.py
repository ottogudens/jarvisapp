"""Procesamiento determinista de plantillas y sus marcadores ``{{campo}}``."""
import io
import re
import zipfile
from pathlib import Path
import unicodedata

# Permite nombres legibles en español (por ejemplo ``{{razón_social}}``), sin
# aceptar espacios ni expresiones ejecutables dentro de los marcadores.
FIELD_RE = re.compile(r"\{\{\s*([^\W\d][\w.-]{0,99})\s*\}\}", re.UNICODE)


def _fields_from_text(text: str) -> list[str]:
    return sorted(set(FIELD_RE.findall(text)))


def _iter_table_paragraphs(table):
    """Itera tablas anidadas de python-docx sin omitir celdas."""
    for row in table.rows:
        for cell in row.cells:
            yield from cell.paragraphs
            for nested in cell.tables:
                yield from _iter_table_paragraphs(nested)


def _docx_paragraphs(document):
    yield from document.paragraphs
    for table in document.tables:
        yield from _iter_table_paragraphs(table)
    for section in document.sections:
        for part in (section.header, section.footer, section.first_page_header,
                     section.first_page_footer, section.even_page_header,
                     section.even_page_footer):
            yield from part.paragraphs
            for table in part.tables:
                yield from _iter_table_paragraphs(table)


def detect_fields(content: bytes, extension: str) -> list[str]:
    """Detecta campos según la semántica real de cada formato.

    No se inspecciona XML OOXML crudo: Word divide frecuentemente un marcador
    entre varios ``runs`` y eso hacía que ``{{cliente}}`` se perdiera.
    """
    extension = extension.lower()
    try:
        if extension in {".docx", ".dotx"}:
            from docx import Document
            document = Document(io.BytesIO(content))
            return _fields_from_text("\n".join(paragraph.text for paragraph in _docx_paragraphs(document)))
        if extension in {".xlsx", ".xltx"}:
            from openpyxl import load_workbook
            workbook = load_workbook(io.BytesIO(content), data_only=False, read_only=True)
            values = (
                str(cell.value) for sheet in workbook.worksheets
                for row in sheet.iter_rows() for cell in row if isinstance(cell.value, str)
            )
            return _fields_from_text("\n".join(values))
        if extension == ".pdf":
            from pypdf import PdfReader
            fields = PdfReader(io.BytesIO(content)).get_fields() or {}
            return sorted(str(name) for name in fields)
        return _fields_from_text(content.decode("utf-8-sig", errors="replace"))
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        raise ValueError(f"No fue posible analizar la plantilla {extension or 'sin extensión'}.") from exc


def _replace_text(value: str, fields: dict) -> str:
    return FIELD_RE.sub(lambda m: str(fields.get(m.group(1), m.group(0))), value)


def _replace_docx_paragraph(paragraph, fields: dict) -> None:
    """Reemplaza incluso un marcador dividido entre runs de Word.

    Los marcadores contenidos en un run conservan completamente su formato. Si
    Word los dividió, se recompone el párrafo para que el documento sea útil;
    el formato de los runs involucrados queda con el estilo del primer run.
    """
    original = "".join(run.text for run in paragraph.runs)
    replacement = _replace_text(original, fields)
    if replacement == original:
        return
    for run in paragraph.runs:
        if FIELD_RE.search(run.text):
            run.text = _replace_text(run.text, fields)
            return
    if paragraph.runs:
        paragraph.runs[0].text = replacement
        for run in paragraph.runs[1:]:
            run.text = ""
    else:
        paragraph.add_run(replacement)


def render_template(content: bytes, filename: str, fields: dict) -> tuple[bytes, str, str]:
    extension = Path(filename).suffix.lower()
    if extension in {".txt", ".md", ".html", ".csv"}:
        mime = {".txt": "text/plain", ".md": "text/markdown", ".html": "text/html", ".csv": "text/csv"}[extension]
        return _replace_text(content.decode("utf-8"), fields).encode("utf-8"), mime, filename
    if extension in {".docx", ".dotx"}:
        from docx import Document
        doc = Document(io.BytesIO(content))
        for paragraph in _docx_paragraphs(doc):
            _replace_docx_paragraph(paragraph, fields)
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
    from pypdf.generic import NameObject
    from reportlab.pdfgen import canvas
    reader = PdfReader(io.BytesIO(content))
    if reader.get_fields():
        raise ValueError("El PDF ya contiene campos rellenables.")
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
    # Un único documento de capas preserva un catálogo AcroForm coherente para
    # todos los campos y páginas; fusionar capas aisladas lo perdía.
    layer = io.BytesIO()
    canvas_obj = canvas.Canvas(layer)
    for number, background in enumerate(reader.pages):
        size = (float(background.mediabox.width), float(background.mediabox.height))
        canvas_obj.setPageSize(size)
        for name, x, y, width, height in by_page.get(number, []):
            canvas_obj.acroForm.textfield(name=name, x=x, y=y, width=width, height=height, borderWidth=1, forceBorder=True)
        canvas_obj.showPage()
    canvas_obj.save(); layer.seek(0)
    form_reader = PdfReader(layer)
    writer = PdfWriter()
    for number, background in enumerate(reader.pages):
        form_page = form_reader.pages[number]
        form_page.merge_page(background)
        writer.add_page(form_page)
    acro_form = form_reader.trailer["/Root"].get("/AcroForm")
    if acro_form:
        writer._root_object[NameObject("/AcroForm")] = acro_form.clone(writer)
    writer.set_need_appearances_writer()
    out = io.BytesIO(); writer.write(out)
    return out.getvalue(), names


_LABEL_FIELDS = {
    "nombre": "nombre_cliente", "cliente": "nombre_cliente", "razon social": "razon_social",
    "rut": "rut_cliente", "dni": "documento_cliente", "email": "email_cliente",
    "correo": "email_cliente", "telefono": "telefono_cliente", "direccion": "direccion_cliente",
    "fecha": "fecha", "patente": "patente", "vin": "vin", "kilometraje": "kilometraje",
    "marca": "marca_vehiculo", "modelo": "modelo_vehiculo", "ano": "ano_vehiculo",
    "diagnostico": "diagnostico", "observaciones": "observaciones", "total": "total",
}


def _normalise_label(value: str) -> str:
    return " ".join("".join(
        char for char in unicodedata.normalize("NFD", value.lower())
        if unicodedata.category(char) != "Mn"
    ).replace("_", " ").split()).rstrip(":")


def _suggested_name(label: str, used: set[str]) -> str | None:
    normalised = _normalise_label(label)
    name = _LABEL_FIELDS.get(normalised)
    if not name:
        return None
    candidate, counter = name, 2
    while candidate in used:
        candidate = f"{name}_{counter}"; counter += 1
    used.add(candidate)
    return candidate


def suggest_fields(content: bytes, extension: str) -> tuple[list[dict], str | None]:
    """Propone campos a partir de etiquetas visibles, sin modificar el archivo."""
    extension = extension.lower()
    if detect_fields(content, extension):
        return [], "La plantilla ya contiene campos. Usa Reprocesar campos para actualizarlos."
    used: set[str] = set()
    suggestions: list[dict] = []
    if extension in {".docx", ".dotx"}:
        from docx import Document
        document = Document(io.BytesIO(content))
        for index, paragraph in enumerate(_docx_paragraphs(document)):
            text = paragraph.text.strip()
            match = re.match(r"^\s*([^:\n]{2,60}):(?:\s*_+)?\s*$", text)
            if match and (name := _suggested_name(match.group(1), used)):
                suggestions.append({"name": name, "label": match.group(1).strip(), "type": "text", "target_index": index})
    elif extension in {".xlsx", ".xltx"}:
        from openpyxl import load_workbook
        workbook = load_workbook(io.BytesIO(content), data_only=False)
        for sheet in workbook.worksheets:
            for row in sheet.iter_rows():
                for cell in row:
                    if not isinstance(cell.value, str):
                        continue
                    if name := _suggested_name(cell.value, used):
                        target = sheet.cell(row=cell.row, column=cell.column + 1)
                        if target.value in (None, ""):
                            suggestions.append({"name": name, "label": cell.value.strip(), "type": "text", "sheet": sheet.title, "cell": target.coordinate})
    elif extension == ".pdf":
        import fitz
        document = fitz.open(stream=content, filetype="pdf")
        for page_number, page in enumerate(document):
            for x0, y0, x1, y1, text, *_ in page.get_text("blocks"):
                match = re.match(r"^\s*([^:\n]{2,60}):\s*$", text.strip())
                if not match or not (name := _suggested_name(match.group(1), used)):
                    continue
                height = float(page.rect.height)
                suggestions.append({
                    "name": name, "label": match.group(1).strip(), "type": "text", "page": page_number,
                    "x": round(float(x1) + 8, 1), "y": round(height - float(y1) - 18, 1),
                    "width": 180.0, "height": 18.0,
                })
        document.close()
    else:
        return [], "La generación asistida está disponible para PDF, Word y Excel."
    return suggestions, None if suggestions else "No se identificaron etiquetas. Agrega campos manualmente o usa un documento con etiquetas como “VIN:”."


def generate_fields(content: bytes, extension: str, fields: list[dict]) -> tuple[bytes, list[str]]:
    """Crea una copia rellenable; nunca modifica la plantilla fuente."""
    extension = extension.lower()
    names = []
    for field in fields:
        name = str(field.get("name", "")).strip()
        if not FIELD_RE.fullmatch("{{" + name + "}}"):
            raise ValueError("Cada campo debe tener un nombre válido (ej.: nombre_cliente).")
        if name in names:
            raise ValueError("Los nombres de campo no pueden repetirse.")
        names.append(name)
    if not names:
        raise ValueError("Selecciona al menos un campo para generar la plantilla.")
    if extension == ".pdf":
        return convert_pdf_to_fillable(content, fields)
    if extension in {".docx", ".dotx"}:
        from docx import Document
        document = Document(io.BytesIO(content))
        paragraphs = list(_docx_paragraphs(document))
        for field in fields:
            index = int(field.get("target_index", -1))
            if index < 0 or index >= len(paragraphs):
                raise ValueError("Una sugerencia de Word ya no corresponde al documento. Vuelve a analizarlo.")
            paragraph = paragraphs[index]
            marker = "{{" + field["name"].strip() + "}}"
            text = paragraph.text
            updated = re.sub(r"_+\s*$", marker, text)
            if updated == text:
                updated = f"{text} {marker}".strip()
            if paragraph.runs:
                paragraph.runs[0].text = updated
                for run in paragraph.runs[1:]: run.text = ""
            else:
                paragraph.add_run(updated)
        output = io.BytesIO(); document.save(output)
        return output.getvalue(), names
    if extension in {".xlsx", ".xltx"}:
        from openpyxl import load_workbook
        workbook = load_workbook(io.BytesIO(content))
        for field in fields:
            sheet = workbook[str(field.get("sheet", ""))]
            cell = sheet[str(field.get("cell", ""))]
            if cell.value not in (None, ""):
                raise ValueError("La celda sugerida ya contiene información. Vuelve a analizar el archivo.")
            cell.value = "{{" + field["name"].strip() + "}}"
        output = io.BytesIO(); workbook.save(output)
        return output.getvalue(), names
    raise ValueError("La generación asistida está disponible para PDF, Word y Excel.")
