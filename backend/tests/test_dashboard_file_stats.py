"""Regresiones de las métricas de archivos del panel principal."""

import ast
from pathlib import Path


def test_dashboard_file_counter_includes_active_knowledge_documents() -> None:
    source = (Path(__file__).resolve().parents[1] / "main.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    endpoint = next(
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "listar_todos_archivos"
    )
    endpoint_source = ast.get_source_segment(source, endpoint) or ""

    assert "KnowledgeDocument.id_tenant == usuario[\"id_tenant\"]" in endpoint_source
    assert "KnowledgeDocument.deleted_at.is_(None)" in endpoint_source
    assert "archivos_subidos + int(documentos_memoria)" in endpoint_source
