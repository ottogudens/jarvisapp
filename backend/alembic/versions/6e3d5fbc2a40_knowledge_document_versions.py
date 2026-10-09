"""Track replacement versions for knowledge documents.

Revision ID: 6e3d5fbc2a40
Revises: 19d6b0ca7ef2
"""
from alembic import op
import sqlalchemy as sa

revision = "6e3d5fbc2a40"
down_revision = "19d6b0ca7ef2"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("knowledge_documents", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("knowledge_documents", sa.Column("replaces_document_id", sa.String(length=36), sa.ForeignKey("knowledge_documents.id_document", ondelete="SET NULL"), nullable=True))


def downgrade():
    op.drop_column("knowledge_documents", "replaces_document_id")
    op.drop_column("knowledge_documents", "version")
