"""Add hierarchical document projects and per-chat knowledge scope.

Revision ID: a9c4e2b7d531
Revises: e7b8c9d0a123
"""
from alembic import op
import sqlalchemy as sa


revision = "a9c4e2b7d531"
down_revision = "e7b8c9d0a123"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "knowledge_folders",
        sa.Column(
            "parent_id",
            sa.String(length=36),
            sa.ForeignKey("knowledge_folders.id_folder", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_knowledge_folders_parent_id", "knowledge_folders", ["parent_id"])
    op.add_column(
        "chat_sessions",
        sa.Column(
            "active_knowledge_folder_id",
            sa.String(length=36),
            sa.ForeignKey("knowledge_folders.id_folder", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_chat_sessions_active_knowledge_folder_id",
        "chat_sessions",
        ["active_knowledge_folder_id"],
    )


def downgrade():
    op.drop_index("ix_chat_sessions_active_knowledge_folder_id", table_name="chat_sessions")
    op.drop_column("chat_sessions", "active_knowledge_folder_id")
    op.drop_index("ix_knowledge_folders_parent_id", table_name="knowledge_folders")
    op.drop_column("knowledge_folders", "parent_id")
