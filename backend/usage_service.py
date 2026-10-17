"""Funciones de agregación para el consumo de IA por organización."""

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.models import AIUsageStats, Usuario


def resolved_token_usage(legacy_tokens: int | None, recorded_tokens: int | None) -> int:
    """Evita duplicar contadores que durante la transición se registran en ambas tablas."""
    return max(int(legacy_tokens or 0), int(recorded_tokens or 0))


def tenant_token_usage(db: Session, tenant_id: int) -> int:
    legacy_tokens = db.query(func.coalesce(func.sum(Usuario.tokens_consumidos), 0)).filter(
        Usuario.id_tenant == tenant_id,
    ).scalar()
    recorded_tokens = db.query(func.coalesce(func.sum(AIUsageStats.tokens_consumidos), 0)).filter(
        AIUsageStats.id_tenant == tenant_id,
    ).scalar()
    return resolved_token_usage(legacy_tokens, recorded_tokens)


def token_usage_by_tenant(db: Session) -> dict[int, int]:
    """Devuelve el mayor contador por tenant para conservar históricos sin doble conteo."""
    legacy_rows = db.query(
        Usuario.id_tenant, func.coalesce(func.sum(Usuario.tokens_consumidos), 0),
    ).group_by(Usuario.id_tenant).all()
    recorded_rows = db.query(
        AIUsageStats.id_tenant, func.coalesce(func.sum(AIUsageStats.tokens_consumidos), 0),
    ).group_by(AIUsageStats.id_tenant).all()
    legacy = {int(tenant_id): int(tokens or 0) for tenant_id, tokens in legacy_rows}
    recorded = {int(tenant_id): int(tokens or 0) for tenant_id, tokens in recorded_rows}
    return {
        tenant_id: resolved_token_usage(legacy.get(tenant_id), recorded.get(tenant_id))
        for tenant_id in legacy.keys() | recorded.keys()
    }
