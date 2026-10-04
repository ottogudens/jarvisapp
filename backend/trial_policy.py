"""Reglas de la prueba gratuita, centralizadas para todos los canales de IA."""
from datetime import datetime, timezone
import os

from fastapi import HTTPException
from sqlalchemy import func

from backend.models import AIUsageStats

TRIAL_DAYS = max(1, int(os.getenv("TRIAL_DAYS", "7")))
TRIAL_DAILY_TOKEN_LIMIT = max(1, int(os.getenv("TRIAL_DAILY_TOKEN_LIMIT", "5000")))


def trial_snapshot(tenant, daily_tokens: int, now: datetime | None = None) -> dict:
    """Calcula el estado de prueba sin depender de una ruta HTTP."""
    now = now or datetime.now(timezone.utc)
    ends_at = getattr(tenant, "trial_ends_at", None)
    if ends_at and ends_at.tzinfo is None:
        ends_at = ends_at.replace(tzinfo=timezone.utc)
    limit = int(getattr(tenant, "trial_daily_token_limit", 0) or 0)
    is_trial = bool(getattr(tenant, "is_trial", False))
    active = not is_trial or (ends_at is not None and now < ends_at)
    return {
        "is_trial": is_trial,
        "trial_active": active,
        "trial_ends_at": ends_at.isoformat() if ends_at else None,
        "daily_token_limit": limit,
        "daily_tokens_used": int(daily_tokens or 0),
        "daily_tokens_remaining": max(0, limit - int(daily_tokens or 0)) if is_trial else None,
    }


def ensure_ai_usage_allowed(db, tenant) -> dict:
    """Bloquea la inferencia al expirar la prueba o llegar al tope diario."""
    daily_tokens = db.query(func.coalesce(func.sum(AIUsageStats.tokens_consumidos), 0)).filter(
        AIUsageStats.id_tenant == tenant.id_tenant,
        func.date(AIUsageStats.fecha_registro) == func.current_date(),
    ).scalar() or 0
    snapshot = trial_snapshot(tenant, daily_tokens)
    if snapshot["is_trial"] and not snapshot["trial_active"]:
        raise HTTPException(status_code=402, detail="Tu prueba gratuita de 7 días finalizó. Elige un plan para continuar usando Bonso.")
    if snapshot["is_trial"] and snapshot["daily_tokens_used"] >= snapshot["daily_token_limit"]:
        raise HTTPException(status_code=429, detail="Alcanzaste el límite diario de tokens de tu prueba. Vuelve mañana o elige un plan.")
    return snapshot
