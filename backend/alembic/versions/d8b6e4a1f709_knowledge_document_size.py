"""Store document byte size for storage quotas and operational metrics.

Revision ID: d8b6e4a1f709
Revises: a12f8e9c4d35
"""
from alembic import op
import sqlalchemy as sa

revision = "d8b6e4a1f709"
down_revision = "a12f8e9c4d35"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("knowledge_documents", sa.Column("byte_size", sa.BigInteger(), nullable=False, server_default="0"))


def downgrade():
    op.drop_column("knowledge_documents", "byte_size")
