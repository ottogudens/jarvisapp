"""Selección local y explicable de perfiles activos para cada consulta."""
import re

STOP_WORDS = {
    "para", "como", "con", "desde", "sobre", "entre", "esta", "este", "estos",
    "estas", "que", "por", "una", "uno", "las", "los", "del", "una", "quiero",
    "puedes", "necesito", "ayuda", "favor", "please", "the", "and", "with",
}


def _terms(value: str) -> set[str]:
    return {term for term in re.findall(r"[a-záéíóúñ0-9_-]{3,}", value.lower()) if term not in STOP_WORDS}


def select_profiles(profiles: list[dict], query: str, max_profiles: int = 2) -> list[dict]:
    """Devuelve perfiles relevantes, preservando el primero como fallback estable.

    No usa IA ni datos externos; por ello la ruta es reproducible y no introduce
    una segunda llamada ni expone la consulta a otro proveedor.
    """
    if not profiles:
        return []
    query_terms = _terms(query)
    ranked = []
    for index, profile in enumerate(profiles):
        name_terms = _terms(profile.get("nombre", ""))
        instruction_terms = _terms(profile.get("instrucciones", ""))
        # El nombre es una señal explícita más fuerte que el texto largo del rol.
        score = 4 * len(query_terms & name_terms) + len(query_terms & instruction_terms)
        ranked.append((score, index, profile))
    matches = [item for item in sorted(ranked, key=lambda item: (-item[0], item[1])) if item[0] > 0]
    if not matches:
        return [profiles[0]]
    return [item[2] for item in matches[:max_profiles]]
