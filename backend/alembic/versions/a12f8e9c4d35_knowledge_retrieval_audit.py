"""Audit RAG retrievals without retaining prompt text.

Revision ID: a12f8e9c4d35
Revises: 6e3d5fbc2a40
"""
from alembic import op
import sqlalchemy as sa

revision = "a12f8e9c4d35"
down_revision = "6e3d5fbc2a40"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "knowledge_retrieval_audit",
        sa.Column("id_audit", sa.String(length=36), primary_key=True),
        sa.Column("id_tenant", sa.Integer(), sa.ForeignKey("saas_tenants.id_tenant", ondelete="CASCADE"), nullable=False),
        sa.Column("id_usuario", sa.Integer(), sa.ForeignKey("usuarios.id_usuario", ondelete="SET NULL"), nullable=True),
        sa.Column("channel", sa.String(length=30), nullable=False, server_default="web"),
        sa.Column("query_sha256", sa.String(length=64), nullable=False),
        sa.Column("result_document_ids", sa.JSON(), nullable=False),
        sa.Column("result_chunk_ids", sa.JSON(), nullable=False),
        sa.Column("result_scores", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_knowledge_retrieval_audit_tenant", "knowledge_retrieval_audit", ["id_tenant"])


def downgrade():
    op.drop_index("ix_knowledge_retrieval_audit_tenant", table_name="knowledge_retrieval_audit")
    op.drop_table("knowledge_retrieval_audit")
