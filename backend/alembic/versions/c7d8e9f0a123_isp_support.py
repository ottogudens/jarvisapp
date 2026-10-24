"""Persist verified ISP support sessions and webhook deduplication.

Merge the two existing migration heads without changing their history.
"""
from alembic import op
import sqlalchemy as sa

revision = 'c7d8e9f0a123'
down_revision = ('b1c2d3e4f5a6', 'a6b7c8d9e0f1')
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('isp_support_sessions',
        sa.Column('id_connection', sa.String(36), sa.ForeignKey('channel_connections.id_connection', ondelete='CASCADE'), primary_key=True),
        sa.Column('customer_phone', sa.String(20), primary_key=True),
        sa.Column('id_tenant', sa.Integer, sa.ForeignKey('saas_tenants.id_tenant', ondelete='CASCADE'), nullable=False),
        sa.Column('id_cliente', sa.Integer, nullable=False),
        sa.Column('verified_by', sa.Integer, sa.ForeignKey('usuarios.id_usuario'), nullable=False),
        sa.Column('state', sa.JSON, nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_isp_support_sessions_id_tenant', 'isp_support_sessions', ['id_tenant'])
    op.create_table('isp_support_events',
        sa.Column('id_connection', sa.String(36), sa.ForeignKey('channel_connections.id_connection', ondelete='CASCADE'), primary_key=True),
        sa.Column('message_id', sa.String(255), primary_key=True),
        sa.Column('status', sa.String(30), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table('isp_support_events')
    op.drop_index('ix_isp_support_sessions_id_tenant', table_name='isp_support_sessions')
    op.drop_table('isp_support_sessions')
