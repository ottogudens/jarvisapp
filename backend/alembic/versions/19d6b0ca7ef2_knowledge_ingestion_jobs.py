"""Add durable background jobs for document indexing.

Revision ID: 19d6b0ca7ef2
Revises: 8b0f7d3e2c11
"""
from alembic import op
import sqlalchemy as sa

revision = "19d6b0ca7ef2"
down_revision = "8b0f7d3e2c11"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "knowledge_ingestion_jobs",
        sa.Column("id_job", sa.String(length=36), primary_key=True),
        sa.Column("id_document", sa.String(length=36), sa.ForeignKey("knowledge_documents.id_document", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="queued"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_knowledge_ingestion_jobs_status", "knowledge_ingestion_jobs", ["status"])


def downgrade():
    op.drop_index("ix_knowledge_ingestion_jobs_status", table_name="knowledge_ingestion_jobs")
    op.drop_table("knowledge_ingestion_jobs")
