"""Add JWT session version for server-side revocation.

Revision ID: f4d5e6a7b809
Revises: e3c4a5d6f708
"""
from alembic import op
import sqlalchemy as sa


revision = "f4d5e6a7b809"
down_revision = "e3c4a5d6f708"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "usuarios",
        sa.Column("session_version", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade():
    op.drop_column("usuarios", "session_version")
