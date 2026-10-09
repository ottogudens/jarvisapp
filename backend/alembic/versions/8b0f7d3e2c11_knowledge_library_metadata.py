"""Add provenance and indexing state to the shared knowledge library.

Revision ID: 8b0f7d3e2c11
Revises: f3d7c1a98b20
"""
from alembic import op
import sqlalchemy as sa

revision = "8b0f7d3e2c11"
down_revision = "f3d7c1a98b20"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("knowledge_documents", sa.Column("storage_path", sa.Text(), nullable=True))
    op.add_column("knowledge_documents", sa.Column("mime_type", sa.String(length=120), nullable=True))
    op.add_column("knowledge_documents", sa.Column("content_sha256", sa.String(length=64), nullable=True))
    op.add_column("knowledge_documents", sa.Column("source_channel", sa.String(length=30), nullable=False, server_default="web"))
    op.add_column("knowledge_documents", sa.Column("status", sa.String(length=20), nullable=False, server_default="processing"))
    op.add_column("knowledge_documents", sa.Column("error_message", sa.Text(), nullable=True))
    op.add_column("knowledge_documents", sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("knowledge_documents", sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_knowledge_documents_content_sha256", "knowledge_documents", ["content_sha256"])
    op.add_column("document_chunks", sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")))


def downgrade():
    op.drop_column("document_chunks", "metadata_json")
    op.drop_index("ix_knowledge_documents_content_sha256", table_name="knowledge_documents")
    for column in ("indexed_at", "chunk_count", "error_message", "status", "source_channel", "content_sha256", "mime_type", "storage_path"):
        op.drop_column("knowledge_documents", column)
