"""Motor de notificaciones por eventos, con reglas y antispam por tenant."""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from backend.crypto_utils import decrypt_secret
from backend.models import NotificationDelivery, NotificationRule, Tenant, Usuario
from backend.telegram_router import send_telegram_message

logger = logging.getLogger("jarvis.notifications")
VALID_OPERATORS = {"equals", "not_equals", "contains", "greater_than", "less_than"}


def _value_at_path(payload: Any, path: str | None) -> Any:
    value = payload
    for part in filter(None, (path or "").lstrip("$").strip(".").split(".")):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def matches(rule: NotificationRule, payload: Any) -> bool:
    """Evalúa una condición sin ejecutar código de usuario."""
    actual = _value_at_path(payload, rule.json_path)
    expected = rule.expected_value or ""
    if rule.operator == "equals":
        return str(actual).lower() == expected.lower()
    if rule.operator == "not_equals":
        return str(actual).lower() != expected.lower()
    if rule.operator == "contains":
        return expected.lower() in str(actual).lower()
    try:
        return float(actual) > float(expected) if rule.operator == "greater_than" else float(actual) < float(expected)
    except (TypeError, ValueError):
        return False


def _can_trigger(rule: NotificationRule, now: datetime) -> bool:
    if not rule.last_triggered_at:
        return True
    last = rule.last_triggered_at
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    return now - last >= timedelta(minutes=max(1, rule.cooldown_minutes))


async def process_event(db: Session, *, user_id: int, source: str, event_key: str, payload: Any) -> int:
    """Procesa un evento y notifica a los usuarios Telegram vinculados del tenant.

    Se registra cada intento. Un fallo de Telegram no interrumpe el consumidor MQTT.
    """
    now = datetime.now(timezone.utc)
    rules = db.query(NotificationRule).filter_by(id_usuario=user_id, source=source, enabled=True).all()
    sent = 0
    for rule in rules:
        if ((rule.topic and rule.topic != event_key)
                or not matches(rule, payload)
                or not _can_trigger(rule, now)):
            continue
        delivery = NotificationDelivery(id_rule=rule.id_rule, id_usuario=user_id, source=source, event_key=event_key)
        db.add(delivery)
        rule.last_triggered_at = now
        db.commit()  # reserva el cooldown antes del envío para evitar duplicados concurrentes

        owner = db.query(Usuario).filter_by(id_usuario=user_id).first()
        tenant: Tenant | None = owner.tenant if owner else None
        recipients = db.query(Usuario).filter(Usuario.id_tenant == owner.id_tenant, Usuario.telegram_chat_id.isnot(None)).all() if owner else []
        if not tenant or not tenant.telegram_bot_token or not recipients:
            delivery.status, delivery.detail = "skipped", "No hay bot o destinatario Telegram vinculado."
            db.commit()
            continue
        actual = _value_at_path(payload, rule.json_path)
        # Sustitución deliberadamente cerrada: una llave escrita por el usuario
        # no debe hacer fallar el envío ni permitir evaluar expresiones.
        message = rule.message_template or "⚠️ {rule}: {value}"
        message = (message.replace("{rule}", rule.nombre)
                          .replace("{value}", str(actual))
                          .replace("{topic}", event_key))
        try:
            token = decrypt_secret(tenant.telegram_bot_token)
            await asyncio.gather(*(send_telegram_message(token, str(user.telegram_chat_id), message) for user in recipients))
            delivery.status, delivery.detail = "sent", f"Entregado a {len(recipients)} destinatario(s)."
            sent += 1
        except Exception:
            logger.exception("No se pudo entregar alerta %s", rule.id_rule)
            delivery.status, delivery.detail = "failed", "No se pudo entregar la notificación."
        db.commit()
    return sent


def process_event_sync(db: Session, **event: Any) -> int:
    """Adaptador seguro para callbacks síncronos de Paho MQTT."""
    return asyncio.run(process_event(db, **event))


def parse_mqtt_payload(raw_payload: str) -> Any:
    try:
        return json.loads(raw_payload)
    except json.JSONDecodeError:
        return raw_payload
