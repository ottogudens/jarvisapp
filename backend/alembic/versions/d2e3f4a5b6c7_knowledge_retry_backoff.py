"""Add retry scheduling to ingestion jobs.

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
"""
from alembic import op
import sqlalchemy as sa


revision = "d2e3f4a5b6c7"
down_revision = "c1d2e3f4a5b6"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("knowledge_ingestion_jobs", sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_knowledge_ingestion_jobs_next_attempt_at", "knowledge_ingestion_jobs", ["next_attempt_at"])


def downgrade():
    op.drop_index("ix_knowledge_ingestion_jobs_next_attempt_at", table_name="knowledge_ingestion_jobs")
    op.drop_column("knowledge_ingestion_jobs", "next_attempt_at")
