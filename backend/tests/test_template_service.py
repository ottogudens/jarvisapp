import io

import pytest

from backend.template_service import detect_fields, render_template


def test_detect_fields_accepts_unicode_names_and_ignores_invalid_markers():
    assert detect_fields("{{razón_social}} {{cliente.1}} {{1invalido}}".encode(), ".txt") == ["cliente.1", "razón_social"]


def test_docx_detects_and_renders_marker_split_between_runs():
    docx = pytest.importorskip("docx")
    document = docx.Document()
    paragraph = document.add_paragraph()
    paragraph.add_run("Estimado {{clien")
    paragraph.add_run("te}}, patente {{patente}}")
    source = io.BytesIO()
    document.save(source)

    assert detect_fields(source.getvalue(), ".docx") == ["cliente", "patente"]
    rendered, _, _ = render_template(source.getvalue(), "contrato.docx", {"cliente": "Ana", "patente": "ABCD12"})
    result = docx.Document(io.BytesIO(rendered))
    assert result.paragraphs[0].text == "Estimado Ana, patente ABCD12"


def test_pdf_fields_are_discovered_from_acroform():
    pypdf = pytest.importorskip("pypdf")
    reportlab = pytest.importorskip("reportlab.pdfgen.canvas")
    source = io.BytesIO()
    canvas = reportlab.Canvas(source)
    canvas.drawString(50, 740, "Formulario")
    canvas.acroForm.textfield(name="vin", x=50, y=700, width=160, height=20)
    canvas.showPage()
    canvas.save()

    assert detect_fields(source.getvalue(), ".pdf") == ["vin"]
