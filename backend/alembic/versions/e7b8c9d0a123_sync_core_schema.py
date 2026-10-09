"""Synchronize the core SaaS schema with the production ORM.

Revision ID: e7b8c9d0a123
Revises: f4d5e6a7b809
"""

from alembic import op


revision = "e7b8c9d0a123"
down_revision = "f4d5e6a7b809"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add fields that were present in the ORM but absent from legacy schemas."""
    # SaaS plan capabilities used by authorization and the admin panel.
    for column in (
        "permite_iot",
        "permite_mikrotik",
        "permite_telegram",
        "permite_whatsapp",
    ):
        op.execute(
            f"ALTER TABLE saas_planes ADD COLUMN IF NOT EXISTS {column} "
            "BOOLEAN DEFAULT FALSE"
        )

    # Tenant-level Telegram credentials are stored encrypted by the application.
    op.execute(
        "ALTER TABLE saas_tenants ADD COLUMN IF NOT EXISTS "
        "telegram_bot_token VARCHAR(200)"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS "
        "ux_saas_tenants_telegram_bot_token "
        "ON saas_tenants (telegram_bot_token) "
        "WHERE telegram_bot_token IS NOT NULL"
    )

    # User authorization and quota fields. Defaults preserve existing accounts.
    op.execute(
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS "
        "rol VARCHAR(20) NOT NULL DEFAULT 'cliente'"
    )
    op.execute(
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS "
        "is_superadmin BOOLEAN NOT NULL DEFAULT FALSE"
    )
    op.execute(
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS "
        "tokens_consumidos INTEGER NOT NULL DEFAULT 0"
    )
    op.execute("ALTER TABLE usuarios ALTER COLUMN perfil_jarvis DROP NOT NULL")
    op.execute(
        "UPDATE usuarios SET rol = 'superadmin' "
        "WHERE is_superadmin = TRUE"
    )


def downgrade() -> None:
    op.drop_index("ux_saas_tenants_telegram_bot_token", table_name="saas_tenants")
    op.drop_column("saas_tenants", "telegram_bot_token")
    op.drop_column("usuarios", "tokens_consumidos")
    op.drop_column("usuarios", "is_superadmin")
    op.drop_column("usuarios", "rol")
    op.drop_column("saas_planes", "permite_whatsapp")
    op.drop_column("saas_planes", "permite_telegram")
    op.drop_column("saas_planes", "permite_mikrotik")
    op.drop_column("saas_planes", "permite_iot")
