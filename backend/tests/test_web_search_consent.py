from backend.web_search_service import (
    confirmation_decision,
    is_informational_query,
)


def test_web_search_requires_an_explicit_affirmative_answer():
    assert confirmation_decision("Sí") is True
    assert confirmation_decision("autorizo la búsqueda") is True
    assert confirmation_decision("no busques") is False
    assert confirmation_decision("cuéntame más") is None


def test_only_informational_queries_trigger_the_web_fallback_offer():
    assert is_informational_query("¿Cuál es el precio actual del cobre?") is True
    assert is_informational_query("Busca información sobre el alternador") is True
    assert is_informational_query("hola") is False
