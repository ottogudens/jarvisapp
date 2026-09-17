"""
Script de migración ONE-OFF: cifra las contraseñas de mikrotik_routers que hoy
están en texto plano.

Uso (una sola vez, después de configurar MIKROTIK_ENCRYPTION_KEY en el entorno
y de desplegar el código con crypto_utils.py):

    python -m backend.migrate_encrypt_router_passwords

Es seguro correrlo más de una vez: decrypt_secret() devuelve el texto tal cual
si no es un token Fernet válido, así que una fila ya cifrada no se vuelve a
cifrar (se detecta con un intento de descifrado).
"""
from backend.database import SessionLocal
from backend.models import MikrotikRouter
from backend.crypto_utils import encrypt_secret, decrypt_secret, _fernet
from cryptography.fernet import InvalidToken


def ya_esta_cifrada(valor: str) -> bool:
    if not _fernet:
        raise RuntimeError("MIKROTIK_ENCRYPTION_KEY no configurada.")
    try:
        _fernet.decrypt(valor.encode())
        return True
    except InvalidToken:
        return False


def main():
    with SessionLocal() as db:
        routers = db.query(MikrotikRouter).all()
        migrados = 0
        for r in routers:
            if not ya_esta_cifrada(r.password):
                r.password = encrypt_secret(r.password)
                migrados += 1
        db.commit()
        print(f"Routers migrados: {migrados} / {len(routers)}")


if __name__ == "__main__":
    main()
