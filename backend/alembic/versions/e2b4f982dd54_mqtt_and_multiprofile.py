"""mqtt_and_multiprofile

Revision ID: e2b4f982dd54
Revises: 321c35a47b37
Create Date: 2026-09-21 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e2b4f982dd54'
down_revision = '321c35a47b37'
branch_labels = None
depends_on = None


def upgrade():
    # 2. Update usuarios
    op.add_column('usuarios', sa.Column('active_profile_ids', sa.JSON(), nullable=True))
    
    # 3. Update iot_configs
    op.add_column('iot_configs', sa.Column('mqtt_auto_connect', sa.Boolean(), server_default='false', nullable=True))
    
    # 4. Create mqtt_subscriptions
    op.create_table('mqtt_subscriptions',
    sa.Column('id_subscription', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('id_usuario', sa.Integer(), nullable=False),
    sa.Column('topic', sa.String(length=255), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['id_usuario'], ['usuarios.id_usuario'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id_subscription')
    )
    op.create_index(op.f('ix_mqtt_subscriptions_id_usuario'), 'mqtt_subscriptions', ['id_usuario'], unique=False)
    
    # 5. Create mqtt_message_cache
    op.create_table('mqtt_message_cache',
    sa.Column('id_message', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('id_usuario', sa.Integer(), nullable=False),
    sa.Column('topic', sa.String(length=255), nullable=False),
    sa.Column('payload', sa.Text(), nullable=False),
    sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['id_usuario'], ['usuarios.id_usuario'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id_message')
    )
    op.create_index(op.f('ix_mqtt_message_cache_id_usuario'), 'mqtt_message_cache', ['id_usuario'], unique=False)
    op.create_index(op.f('ix_mqtt_message_cache_topic'), 'mqtt_message_cache', ['topic'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_mqtt_message_cache_topic'), table_name='mqtt_message_cache')
    op.drop_index(op.f('ix_mqtt_message_cache_id_usuario'), table_name='mqtt_message_cache')
    op.drop_table('mqtt_message_cache')
    op.drop_index(op.f('ix_mqtt_subscriptions_id_usuario'), table_name='mqtt_subscriptions')
    op.drop_table('mqtt_subscriptions')
    op.drop_column('iot_configs', 'mqtt_auto_connect')
    op.drop_column('usuarios', 'active_profile_ids')
