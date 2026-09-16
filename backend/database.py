"""
J.A.R.V.I.S. SaaS — Conexión a Base de Datos

Correcciones aplicadas:
- Fix #18: Validación explícita de DATABASE_URL con mensaje de error claro
"""

import os
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.models import Base

# ---------------------------------------------------------------------------
# Configuración del Engine (Fix #18: validar que DATABASE_URL no sea None)
# ---------------------------------------------------------------------------

DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
    elif DATABASE_URL.startswith("postgresql://"):
        DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

if not DATABASE_URL:
    print(
        "===============================================================\n"
        "  ERROR FATAL: DATABASE_URL no esta configurada.\n"
        "  Configure la variable de entorno apuntando a PostgreSQL.\n"
        "  Ejemplo: postgresql://user:password@host:5432/jarvis_db\n"
        "==============================================================="
    )
    sys.exit(1)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ---------------------------------------------------------------------------
# Funciones públicas
# ---------------------------------------------------------------------------

from sqlalchemy import text

def inicializar_base_de_datos_remota():
    """
    Crea todas las tablas definidas en models.py si no existen.
    Para migraciones incrementales en producción, usar Alembic.
    """
    try:
        with engine.connect() as conn:
            conn.execute(text('CREATE EXTENSION IF NOT EXISTS vector;'))
            conn.commit()
    except Exception as e:
        print(f"Error inicializando vector: {e}")

    # Migración manual para nuevas columnas de IA (Transacciones separadas)
    try:
        with engine.connect() as conn:
            conn.execute(text('ALTER TABLE saas_tenants ADD COLUMN ai_provider VARCHAR DEFAULT \'gemini\''))
            conn.commit()
    except Exception:
        pass
        
    try:
        with engine.connect() as conn:
            conn.execute(text('ALTER TABLE saas_tenants ADD COLUMN ai_model VARCHAR DEFAULT \'gemini-1.5-flash\''))
            conn.commit()
    except Exception:
        pass

    try:
        with engine.connect() as conn:
            conn.execute(text('ALTER TABLE saas_tenants ADD COLUMN nombre_contacto VARCHAR(150)'))
            conn.execute(text('ALTER TABLE saas_tenants ADD COLUMN telefono VARCHAR(50)'))
            conn.commit()
    except Exception:
        pass
        
    try:
        with engine.connect() as conn:
            conn.execute(text('ALTER TABLE usuarios ALTER COLUMN perfil_jarvis DROP NOT NULL'))
            conn.execute(text('ALTER TABLE usuarios ADD COLUMN active_profile_id INTEGER'))
            conn.commit()
    except Exception:
        pass

    try:
        with engine.connect() as conn:
            conn.execute(text('ALTER TABLE mikrotik_routers ADD COLUMN is_connected BOOLEAN DEFAULT FALSE'))
            conn.execute(text('ALTER TABLE mikrotik_routers ADD COLUMN last_error VARCHAR(255)'))
            conn.commit()
    except Exception:
        pass
        
    Base.metadata.create_all(bind=engine)


def get_db():
    """Dependency de FastAPI: genera una sesión de BD por request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
