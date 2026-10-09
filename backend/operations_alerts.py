"""Alertas operativas sin incluir texto ni archivos de clientes."""
from __future__ import annotations

import hashlib
import os
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy.orm import Session

from backend.models import KnowledgeIngestionJob, KnowledgeRetrievalAudit, SystemSettings, TelegramWebhookEvent

HEARTBEAT_KEY = "KNOWLEDGE_WORKER_HEARTBEAT"
CHECK_INTERVAL_SECONDS = 60
RETENTION_CHECK_KEY = "OPERATIONAL_RETENTION_LAST_RUN"
RETENTION_CHECK_INTERVAL = timedelta(hours=24)


def _retention_days(name: str, default: int) -> int:
    """Lee una retención conservadora y evita valores accidentales peligrosos."""
    try:
        return min(3650, max(1, int(os.getenv(name, str(default)))))
    except ValueError:
        return default


def cleanup_operational_data(db: Session) -> dict[str, int]:
    """Borra telemetría vencida, nunca documentos, conversaciones ni cuentas."""
    now = datetime.now(timezone.utc)
    setting = db.query(SystemSettings).filter_by(key=RETENTION_CHECK_KEY).first()
    if setting:
        try:
            previous = datetime.fromisoformat(setting.value)
            if previous.tzinfo is None:
                previous = previous.replace(tzinfo=timezone.utc)
            if now - previous < RETENTION_CHECK_INTERVAL:
                return {"audits": 0, "webhook_events": 0}
        except ValueError:
            pass
    audit_cutoff = now - timedelta(days=_retention_days("RAG_AUDIT_RETENTION_DAYS", 90))
    webhook_cutoff = now - timedelta(days=_retention_days("TELEGRAM_WEBHOOK_RETENTION_DAYS", 30))
    audits = db.query(KnowledgeRetrievalAudit).filter(
        KnowledgeRetrievalAudit.created_at < audit_cutoff,
    ).delete(synchronize_session=False)
    webhook_events = db.query(TelegramWebhookEvent).filter(
        TelegramWebhookEvent.status == "completed",
        TelegramWebhookEvent.processed_at < webhook_cutoff,
    ).delete(synchronize_session=False)
    if setting:
        setting.value = now.isoformat()
    else:
        db.add(SystemSettings(key=RETENTION_CHECK_KEY, value=now.isoformat()))
    db.commit()
    return {"audits": audits, "webhook_events": webhook_events}


def record_worker_heartbeat(db: Session) -> None:
    now = datetime.now(timezone.utc).isoformat()
    setting = db.query(SystemSettings).filter_by(key=HEARTBEAT_KEY).first()
    if setting:
        setting.value = now
    else:
        db.add(SystemSettings(key=HEARTBEAT_KEY, value=now))
    db.commit()


def _operational_messages(db: Session) -> list[str]:
    now = datetime.now(timezone.utc)
    stale_before = now - timedelta(minutes=15)
    processing = db.query(KnowledgeIngestionJob).filter_by(status="processing").all()
    failed = db.query(KnowledgeIngestionJob).filter_by(status="failed").count()
    queued = db.query(KnowledgeIngestionJob).filter_by(status="queued").count()
    messages = []
    stale = [job for job in processing if job.started_at and job.started_at < stale_before]
    if stale:
        messages.append(f"{len(stale)} trabajo(s) documental(es) lleva(n) más de 15 minutos procesando.")
    if failed:
        messages.append(f"{failed} trabajo(s) documental(es) fallaron y requieren revisión.")
    if queued >= 20:
        messages.append(f"La cola documental tiene {queued} trabajo(s) pendientes.")
    return messages


def _allowed_to_send(db: Session, message: str) -> bool:
    """Suprime repetición del mismo aviso durante el intervalo configurado."""
    cooldown = max(5, int(os.getenv("OPERATIONS_ALERT_COOLDOWN_MINUTES", "30")))
    digest = hashlib.sha256(message.encode("utf-8")).hexdigest()[:24]
    key = f"OPS_ALERT_{digest}"
    setting = db.query(SystemSettings).filter_by(key=key).first()
    now = datetime.now(timezone.utc)
    if setting:
        try:
            previous = datetime.fromisoformat(setting.value)
            if previous.tzinfo is None:
                previous = previous.replace(tzinfo=timezone.utc)
            if now - previous < timedelta(minutes=cooldown):
                return False
        except ValueError:
            pass
        setting.value = now.isoformat()
    else:
        db.add(SystemSettings(key=key, value=now.isoformat()))
    db.commit()
    return True


async def dispatch_operational_alerts(db: Session) -> int:
    """Envía avisos configurados; no falla ni detiene el worker si un canal cae."""
    messages = _operational_messages(db)
    if not messages:
        return 0
    webhook = os.getenv("OPERATIONS_ALERT_WEBHOOK_URL", "").strip()
    telegram_token = os.getenv("ADMIN_ALERT_TELEGRAM_BOT_TOKEN", "").strip()
    telegram_chat = os.getenv("ADMIN_ALERT_TELEGRAM_CHAT_ID", "").strip()
    if not webhook and not (telegram_token and telegram_chat):
        return 0
    sent = 0
    async with httpx.AsyncClient(timeout=10) as client:
        for message in messages:
            if not _allowed_to_send(db, message):
                continue
            body = f"⚠️ Bonso · Alerta operativa\n{message}"
            try:
                if webhook:
                    response = await client.post(webhook, json={"text": body})
                    response.raise_for_status()
                if telegram_token and telegram_chat:
                    response = await client.post(
                        f"https://api.telegram.org/bot{telegram_token}/sendMessage",
                        json={"chat_id": telegram_chat, "text": body},
                    )
                    response.raise_for_status()
                sent += 1
            except httpx.HTTPError:
                # La alerta se volverá a intentar tras el cooldown y el worker
                # nunca queda bloqueado por una integración externa caída.
                continue
    return sent
