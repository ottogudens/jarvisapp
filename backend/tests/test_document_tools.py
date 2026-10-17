from pathlib import Path


def test_document_tools_expose_folder_and_file_listing_for_all_channels():
    source = (Path(__file__).resolve().parents[1] / "ai_service.py").read_text(encoding="utf-8")

    for tool_name in ("listar_carpetas_documentales", "listar_documentos_conocimiento", "seleccionar_carpeta_documental"):
        assert f'"name": "{tool_name}"' in source
