"""Add visible ingestion progress to document jobs.

Revision ID: c1d2e3f4a5b6
Revises: a9c4e2b7d531
"""
from alembic import op
import sqlalchemy as sa


revision = "c1d2e3f4a5b6"
down_revision = "a9c4e2b7d531"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("knowledge_ingestion_jobs", sa.Column("stage", sa.String(length=40), nullable=False, server_default="queued"))
    op.add_column("knowledge_ingestion_jobs", sa.Column("progress_percent", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("knowledge_ingestion_jobs", sa.Column("total_chunks", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("knowledge_ingestion_jobs", sa.Column("processed_chunks", sa.Integer(), nullable=False, server_default="0"))
    op.alter_column("knowledge_ingestion_jobs", "stage", server_default=None)
    op.alter_column("knowledge_ingestion_jobs", "progress_percent", server_default=None)
    op.alter_column("knowledge_ingestion_jobs", "total_chunks", server_default=None)
    op.alter_column("knowledge_ingestion_jobs", "processed_chunks", server_default=None)


def downgrade():
    op.drop_column("knowledge_ingestion_jobs", "processed_chunks")
    op.drop_column("knowledge_ingestion_jobs", "total_chunks")
    op.drop_column("knowledge_ingestion_jobs", "progress_percent")
    op.drop_column("knowledge_ingestion_jobs", "stage")
