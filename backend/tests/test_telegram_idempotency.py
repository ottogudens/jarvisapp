import os
from datetime import datetime, timezone
from unittest.mock import MagicMock

# El router carga la fábrica de sesiones al importarse; no se conecta durante
# estas pruebas unitarias, pero necesita una URL sintácticamente válida.
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/jarvis_test")

from backend.models import TelegramWebhookEvent
from backend.telegram_router import _claim_telegram_update


def _db_with_event(event=None):
    db = MagicMock()
    query = db.query.return_value
    query.filter_by.return_value.first.return_value = event
    return db


def test_claim_creates_a_ledger_entry_for_new_update():
    db = _db_with_event()

    event = _claim_telegram_update(db, tenant_id=7, update_id=12345)

    assert event is not None
    assert event.id_tenant == 7
    assert event.update_id == 12345
    assert event.status == "processing"
    db.add.assert_called_once_with(event)
    db.commit.assert_called_once()


def test_claim_rejects_completed_delivery():
    event = TelegramWebhookEvent(
        id_tenant=7, update_id=12345, status="completed",
        created_at=datetime.now(timezone.utc),
    )
    db = _db_with_event(event)

    assert _claim_telegram_update(db, tenant_id=7, update_id=12345) is None
    db.add.assert_not_called()
    db.commit.assert_not_called()
