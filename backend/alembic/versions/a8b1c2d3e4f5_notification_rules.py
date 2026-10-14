"""notification rules and delivery audit

Revision ID: a8b1c2d3e4f5
Revises: a6b7c8d9e0f1, e3f4a5b6c7d8
Create Date: 2026-10-13 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "a8b1c2d3e4f5"
# Une las dos ramas que ya existían (planes e historial documental). Esto
# mantiene un único `head`, necesario porque Railway arranca con
# `alembic upgrade head`.
down_revision = ("a6b7c8d9e0f1", "e3f4a5b6c7d8")
branch_labels = None
depends_on = None


def upgrade():
    # El worker puede haber arrancado antes que la API y ejecutar
    # Base.metadata.create_all(). Por eso verificamos la existencia antes de
    # crear: la migración sigue marcándose correctamente sin fallar al reinicio.
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("notification_rules"):
        op.create_table(
            "notification_rules",
            sa.Column("id_rule", sa.String(36), primary_key=True),
            sa.Column("id_usuario", sa.Integer(), sa.ForeignKey("usuarios.id_usuario", ondelete="CASCADE"), nullable=False),
            sa.Column("nombre", sa.String(120), nullable=False),
            sa.Column("source", sa.String(30), nullable=False, server_default="mqtt"),
            sa.Column("topic", sa.String(255)), sa.Column("json_path", sa.String(255)),
            sa.Column("operator", sa.String(20), nullable=False, server_default="equals"),
            sa.Column("expected_value", sa.Text()), sa.Column("message_template", sa.Text()),
            sa.Column("cooldown_minutes", sa.Integer(), nullable=False, server_default="15"),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("last_triggered_at", sa.DateTime(timezone=True)),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        )
    inspector = sa.inspect(op.get_bind())
    rule_indexes = {index["name"] for index in inspector.get_indexes("notification_rules")}
    if "ix_notification_rules_id_usuario" not in rule_indexes:
        op.create_index("ix_notification_rules_id_usuario", "notification_rules", ["id_usuario"])

    if not inspector.has_table("notification_deliveries"):
        op.create_table(
            "notification_deliveries",
            sa.Column("id_delivery", sa.String(36), primary_key=True),
            sa.Column("id_rule", sa.String(36), sa.ForeignKey("notification_rules.id_rule", ondelete="SET NULL")),
            sa.Column("id_usuario", sa.Integer(), sa.ForeignKey("usuarios.id_usuario", ondelete="SET NULL")),
            sa.Column("source", sa.String(30), nullable=False), sa.Column("event_key", sa.String(255), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="pending"), sa.Column("detail", sa.Text()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        )
    inspector = sa.inspect(op.get_bind())
    delivery_indexes = {index["name"] for index in inspector.get_indexes("notification_deliveries")}
    if "ix_notification_deliveries_id_rule" not in delivery_indexes:
        op.create_index("ix_notification_deliveries_id_rule", "notification_deliveries", ["id_rule"])
    if "ix_notification_deliveries_id_usuario" not in delivery_indexes:
        op.create_index("ix_notification_deliveries_id_usuario", "notification_deliveries", ["id_usuario"])


def downgrade():
    op.drop_table("notification_deliveries")
    op.drop_table("notification_rules")
