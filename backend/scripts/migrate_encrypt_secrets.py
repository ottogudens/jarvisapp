"""Cifra secretos históricos almacenados en PostgreSQL.

Ejecutar una sola vez en un entorno controlado, tras configurar
APP_ENCRYPTION_KEY y antes de revocar la clave previa. El script es idempotente:
descifra valores Fernet existentes o trata valores heredados como texto plano,
y los vuelve a cifrar con la clave activa.
"""

import os
import sys

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from dotenv import load_dotenv

load_dotenv(os.path.join(project_root, ".env"))

from backend.crypto_utils import decrypt_secret, encrypt_secret
from backend.database import SessionLocal
from backend.models import IoTConfig, SystemSettings, Tenant


SECRET_SETTING_KEYS = {
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "DEEPSEEK_API_KEY",
    "GEMINI_API_KEY",
}


def reencrypt(value: str | None) -> str | None:
    if not value:
        return value
    return encrypt_secret(decrypt_secret(value))


def migrate():
    if not os.getenv("APP_ENCRYPTION_KEY"):
        raise RuntimeError("APP_ENCRYPTION_KEY es obligatoria para migrar secretos.")
    if os.getenv("CONFIRM_ENCRYPTION_MIGRATION") != "ENCRYPT_EXISTING_SECRETS":
        raise RuntimeError(
            "Defina CONFIRM_ENCRYPTION_MIGRATION=ENCRYPT_EXISTING_SECRETS para continuar."
        )

    db = SessionLocal()
    try:
        migrated = 0
        for config in db.query(IoTConfig).all():
            config.ha_token = reencrypt(config.ha_token)
            config.mqtt_password = reencrypt(config.mqtt_password)
            migrated += int(bool(config.ha_token)) + int(bool(config.mqtt_password))

        for tenant in db.query(Tenant).all():
            tenant.telegram_bot_token = reencrypt(tenant.telegram_bot_token)
            migrated += int(bool(tenant.telegram_bot_token))

        settings = db.query(SystemSettings).filter(SystemSettings.key.in_(SECRET_SETTING_KEYS)).all()
        for setting in settings:
            setting.value = reencrypt(setting.value)
            migrated += int(bool(setting.value))

        db.commit()
        print(f"Migración completada: {migrated} secretos cifrados.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    migrate()
