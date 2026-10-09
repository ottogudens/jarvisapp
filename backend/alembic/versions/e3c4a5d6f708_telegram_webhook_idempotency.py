"""Add idempotency ledger for Telegram webhook deliveries.

Revision ID: e3c4a5d6f708
Revises: b7c2e5f1a048
"""
from alembic import op
import sqlalchemy as sa


revision = "e3c4a5d6f708"
down_revision = "b7c2e5f1a048"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "telegram_webhook_events",
        sa.Column("id_event", sa.String(length=36), nullable=False),
        sa.Column("id_tenant", sa.Integer(), nullable=False),
        sa.Column("update_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="processing"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["id_tenant"], ["saas_tenants.id_tenant"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id_event"),
        sa.UniqueConstraint("id_tenant", "update_id", name="uq_telegram_event_tenant_update"),
    )
    op.create_index("ix_telegram_webhook_events_id_tenant", "telegram_webhook_events", ["id_tenant"])
    op.create_index("ix_telegram_webhook_events_status", "telegram_webhook_events", ["status"])


def downgrade():
    op.drop_index("ix_telegram_webhook_events_status", table_name="telegram_webhook_events")
    op.drop_index("ix_telegram_webhook_events_id_tenant", table_name="telegram_webhook_events")
    op.drop_table("telegram_webhook_events")
