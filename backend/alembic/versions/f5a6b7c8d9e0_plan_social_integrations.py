"""Add social and workspace plan capabilities.

Revision ID: f5a6b7c8d9e0
Revises: e3f4a5b6c7d8
"""
from alembic import op


revision = "f5a6b7c8d9e0"
down_revision = "e3f4a5b6c7d8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for column in ("permite_google_workspace", "permite_facebook", "permite_instagram", "permite_tiktok"):
        op.execute(f"ALTER TABLE saas_planes ADD COLUMN IF NOT EXISTS {column} BOOLEAN NOT NULL DEFAULT FALSE")


def downgrade() -> None:
    for column in ("permite_tiktok", "permite_instagram", "permite_facebook", "permite_google_workspace"):
        op.execute(f"ALTER TABLE saas_planes DROP COLUMN IF EXISTS {column}")
