"""Add document quotas to SaaS plans.

Revision ID: b7c2e5f1a048
Revises: d8b6e4a1f709
"""
from alembic import op
import sqlalchemy as sa

revision = "b7c2e5f1a048"
down_revision = "d8b6e4a1f709"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("saas_planes", sa.Column("max_documentos", sa.Integer(), nullable=False, server_default="100"))
    op.add_column("saas_planes", sa.Column("almacenamiento_bytes", sa.BigInteger(), nullable=False, server_default="1073741824"))
    op.add_column("saas_planes", sa.Column("max_upload_bytes", sa.BigInteger(), nullable=False, server_default="15728640"))


def downgrade():
    op.drop_column("saas_planes", "max_upload_bytes")
    op.drop_column("saas_planes", "almacenamiento_bytes")
    op.drop_column("saas_planes", "max_documentos")
