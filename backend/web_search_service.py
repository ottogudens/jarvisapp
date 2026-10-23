"""Búsqueda web bajo consentimiento explícito del usuario."""

from __future__ import annotations

import os
import re
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy.orm import Session

from backend.crypto_utils import decrypt_secret
from backend.models import SystemSettings


WEB_SEARCH_CONSENT_TTL = timedelta(minutes=15)
_CONFIRMATIONS = {"si", "sí", "s", "ok", "dale", "acepto", "autorizo", "confirmo", "procede", "adelante"}
_REJECTIONS = {"no", "cancelar", "cancela", "no autorizo", "no busques"}


def confirmation_decision(text: str) -> bool | None:
    """True acepta, False rechaza y None no es una respuesta de consentimiento."""
    normalized = re.sub(r"[^a-záéíóúñ ]", "", (text or "").lower()).strip()
    if normalized in _CONFIRMATIONS or normalized.startswith(("sí busca", "si busca", "autorizo la búsqueda", "puedes buscar")):
        return True
    if normalized in _REJECTIONS or normalized.startswith(("no busques", "no autorizo", "cancela")):
        return False
    return None


def is_informational_query(text: str) -> bool:
    """Evita pedir permiso para saludos o mensajes cortos sin una consulta real."""
    normalized = (text or "").strip()
    words = re.findall(r"\w+", normalized, flags=re.UNICODE)
    if len(words) < 3:
        return False
    return "?" in normalized or any(token.lower() in {
        "busca", "buscar", "información", "informacion", "qué", "que", "cuál", "cual",
        "cómo", "como", "cuándo", "cuando", "dónde", "donde", "precio", "noticias",
    } for token in words)


def pending_search_is_valid(pending_at: datetime | None) -> bool:
    if not pending_at:
        return False
    if pending_at.tzinfo is None:
        pending_at = pending_at.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - pending_at <= WEB_SEARCH_CONSENT_TTL


def tavily_api_key(db: Session) -> str:
    setting = db.query(SystemSettings).filter(SystemSettings.key == "TAVILY_API_KEY").first()
    if setting and setting.value:
        return decrypt_secret(setting.value)
    return os.getenv("TAVILY_API_KEY", "")


async def search_web(db: Session, query: str, max_results: int = 5) -> tuple[str, list[dict]]:
    """Busca mediante Tavily y devuelve contexto delimitado y fuentes para el LLM."""
    api_key = tavily_api_key(db)
    if not api_key:
        raise RuntimeError("La búsqueda web no está configurada. Solicita al administrador una clave Tavily.")
    payload = {
        "api_key": api_key,
        "query": query,
        "search_depth": "basic",
        "max_results": max_results,
        "include_answer": False,
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post("https://api.tavily.com/search", json=payload)
    response.raise_for_status()
    results = response.json().get("results", [])[:max_results]
    if not results:
        return "", []
    sources = [
        {"title": item.get("title", "Fuente web"), "url": item.get("url", "")}
        for item in results if item.get("url")
    ]
    context = "\n\n".join(
        f"[FUENTE WEB: {item.get('title', 'Sin título')} | {item.get('url', '')}]\n{item.get('content', '')}"
        for item in results
    )
    return context, sources
