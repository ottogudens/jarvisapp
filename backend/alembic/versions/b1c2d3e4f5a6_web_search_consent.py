"""Add explicit web-search consent to chat sessions.

Revision ID: b1c2d3e4f5a6
Revises: a8b1c2d3e4f5
"""
from alembic import op
import sqlalchemy as sa


revision = "b1c2d3e4f5a6"
down_revision = "a8b1c2d3e4f5"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("chat_sessions")}
    if "web_search_pending_query" not in columns:
        op.add_column("chat_sessions", sa.Column("web_search_pending_query", sa.Text(), nullable=True))
    if "web_search_pending_at" not in columns:
        op.add_column("chat_sessions", sa.Column("web_search_pending_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("chat_sessions", "web_search_pending_at")
    op.drop_column("chat_sessions", "web_search_pending_query")
