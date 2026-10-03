"""Add an authenticated Telegram webhook secret.

Revision ID: c4a1f9b2d6e0
Revises: e2b4f982dd54
Create Date: 2026-10-02 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "c4a1f9b2d6e0"
down_revision = "e2b4f982dd54"
branch_labels = None
depends_on = None


def upgrade():
    # Compatible con las instalaciones existentes que todavía ejecutan la
    # inicialización transitoria de esquema al arrancar.
    op.execute(
        "ALTER TABLE saas_tenants "
        "ADD COLUMN IF NOT EXISTS telegram_webhook_secret VARCHAR(128)"
    )


def downgrade():
    op.execute("ALTER TABLE saas_tenants DROP COLUMN IF EXISTS telegram_webhook_secret")
