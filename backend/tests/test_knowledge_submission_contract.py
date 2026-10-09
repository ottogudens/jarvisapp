"""Regresiones del contrato de ingreso documental compartido por los canales."""

import ast
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("relative_path", ["backend/main.py", "backend/telegram_router.py"])
def test_submit_document_is_called_with_keyword_only_arguments(relative_path: str) -> None:
    """`submit_document` acepta **kwargs; web y Telegram no deben pasar `db` posicional."""
    tree = ast.parse((ROOT / relative_path).read_text(encoding="utf-8"))
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "submit_document"
    ]

    assert calls, f"No se encontró submit_document en {relative_path}"
    for call in calls:
        assert not call.args, f"{relative_path}:{call.lineno} usa argumentos posicionales"
        assert any(keyword.arg == "db" for keyword in call.keywords)
