"""
Cifrado simétrico para credenciales sensibles (contraseñas de routers MikroTik).

Requiere la variable de entorno MIKROTIK_ENCRYPTION_KEY con una clave Fernet
válida. Generar una nueva con:

    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

Guarda esa clave en las variables de entorno de Railway (o el secret manager que uses),
NUNCA en el repo ni en .env versionado.
"""
import os
from cryptography.fernet import Fernet, InvalidToken

_KEY = os.getenv("MIKROTIK_ENCRYPTION_KEY")
_fernet = Fernet(_KEY.encode()) if _KEY else None


def encrypt_secret(plaintext: str) -> str:
    if not _fernet:
        raise RuntimeError(
            "MIKROTIK_ENCRYPTION_KEY no está configurada. No se pueden guardar "
            "credenciales de router sin cifrado."
        )
    return _fernet.encrypt(plaintext.encode()).decode()


def decrypt_secret(ciphertext: str) -> str:
    if not _fernet:
        raise RuntimeError("MIKROTIK_ENCRYPTION_KEY no está configurada.")
    try:
        return _fernet.decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        # Compatibilidad con filas antiguas guardadas en texto plano antes de esta
        # migración: si no es un token Fernet válido, se asume texto plano legado
        # y se retorna tal cual (permite migración gradual, ver migrate_passwords.py).
        return ciphertext
