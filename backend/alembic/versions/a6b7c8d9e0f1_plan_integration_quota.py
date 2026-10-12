"""Add integration quota to SaaS plans.

Revision ID: a6b7c8d9e0f1
Revises: f5a6b7c8d9e0
"""
from alembic import op

revision = "a6b7c8d9e0f1"
down_revision = "f5a6b7c8d9e0"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute("ALTER TABLE saas_planes ADD COLUMN IF NOT EXISTS max_integraciones INTEGER NOT NULL DEFAULT 0")

def downgrade() -> None:
    op.execute("ALTER TABLE saas_planes DROP COLUMN IF EXISTS max_integraciones")
