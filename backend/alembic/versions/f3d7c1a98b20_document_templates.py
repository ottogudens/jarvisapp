"""Add tenant document templates.

Revision ID: f3d7c1a98b20
Revises: c4a1f9b2d6e0
"""
from alembic import op
import sqlalchemy as sa

revision = "f3d7c1a98b20"
down_revision = "c4a1f9b2d6e0"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("document_templates", sa.Column("id_template", sa.String(36), primary_key=True), sa.Column("id_tenant", sa.Integer(), sa.ForeignKey("saas_tenants.id_tenant", ondelete="CASCADE"), nullable=False), sa.Column("id_usuario", sa.Integer(), sa.ForeignKey("usuarios.id_usuario", ondelete="SET NULL")), sa.Column("nombre", sa.String(255), nullable=False), sa.Column("extension", sa.String(12), nullable=False), sa.Column("contenido_base64", sa.Text(), nullable=False), sa.Column("campos", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")))
    op.create_index("ix_document_templates_tenant", "document_templates", ["id_tenant"])

def downgrade():
    op.drop_index("ix_document_templates_tenant", table_name="document_templates")
    op.drop_table("document_templates")
