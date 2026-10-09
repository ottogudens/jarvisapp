import io

import pytest

from backend.knowledge_service import chunk_text, chunks_with_provenance, extract_text, knowledge_mime_type


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("manual.pdf", "application/pdf"),
        ("manual.txt", "text/plain"),
        ("manual.md", "text/markdown"),
        ("stock.csv", "text/csv"),
        ("manual.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        ("stock.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    ],
)
def test_knowledge_mime_type_uses_canonical_type_for_supported_extensions(filename, expected):
    assert knowledge_mime_type(filename, "application/octet-stream") == expected


def test_extracts_docx_text_and_table():
    docx = pytest.importorskip("docx")
    Document = docx.Document
    document = Document()
    document.add_heading("Procedimiento", 1)
    document.add_paragraph("Validar presión antes de iniciar.")
    table = document.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text = "Equipo"
    table.rows[0].cells[1].text = "Estado"
    output = io.BytesIO()
    document.save(output)

    text, provenance = extract_text("manual.docx", output.getvalue())

    assert "Validar presión" in text
    assert "Equipo | Estado" in text
    assert provenance == [{"section": "document"}]


def test_extracts_excel_with_sheet_and_rows():
    openpyxl = pytest.importorskip("openpyxl")
    Workbook = openpyxl.Workbook
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Inventario"
    sheet.append(["SKU", "Stock"])
    sheet.append(["A-10", 7])
    output = io.BytesIO()
    workbook.save(output)

    text, provenance = extract_text("inventario.xlsx", output.getvalue())

    assert "[Hoja: Inventario]" in text
    assert "Fila 2: A-10 | 7" in text
    assert provenance == [{"sheet": "Inventario"}]


def test_chunks_preserve_all_text():
    text = "A" * 900 + "\n\n" + "B" * 900
    chunks = chunk_text(text)
    assert len(chunks) == 2
    assert "".join(chunks).replace("\n", "") == text.replace("\n", "")


def test_extracts_csv_without_external_parser():
    text, provenance = extract_text("stock.csv", b"sku;stock\nA-10;7\n")
    assert "Fila 2: A-10 | 7" in text
    assert provenance == [{"section": "csv"}]


def test_chunks_keep_csv_provenance():
    chunks = chunks_with_provenance("stock.csv", b"sku;stock\nA-10;7\n")
    assert chunks[0][1] == {"section": "csv"}
    assert "A-10" in chunks[0][0]
