"""
SCRIPT DE RESET COMPLETO — Uso único en producción.

Elimina TODOS los datos existentes (tenants, usuarios, sesiones, etc.)
y crea un único usuario SuperAdmin con los datos correctos.

Uso:
    python -m backend.scripts.reset_superadmin

⚠️  ESTE SCRIPT ES DESTRUCTIVO E IRREVERSIBLE.
"""

import os
import sys

# Agregar el root del proyecto al path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from dotenv import load_dotenv
load_dotenv(os.path.join(project_root, ".env"))

from sqlalchemy import text
from backend.database import engine, SessionLocal
from backend.models import (
    Base, SaaSPlan, Tenant, Usuario, ROL_SUPERADMIN,
    TenantProfile, JarvisProfile
)
from backend.auth import hash_password

# ──────────────────────────────────────────────────────────────
# DATOS DEL SUPERADMIN CORRECTO
# ──────────────────────────────────────────────────────────────
SUPERADMIN = {
    "nombre_organizacion": "Skale",
    "nombre_contacto": "Otto Gudenschwager",
    "telefono": "+56990819881",
    "email": "admin@skale.cl",
    "password": "GuD3Ns@#",
}


def reset():
    print("=" * 60)
    print("  RESET COMPLETO DE BASE DE DATOS")
    print("=" * 60)
    print(f"\n  SuperAdmin a crear: {SUPERADMIN['email']}")
    print(f"  Organización      : {SUPERADMIN['nombre_organizacion']}")
    print(f"  Contacto          : {SUPERADMIN['nombre_contacto']}")
    print()

    confirm = input("  ⚠️  ¿Confirmar eliminación de TODOS los datos? (escribe 'CONFIRMAR'): ")
    if confirm.strip() != "CONFIRMAR":
        print("  Operación cancelada.")
        return

    print("\n  Iniciando reset...")

    with engine.connect() as conn:
        # Deshabilitar FK checks temporalmente para poder truncar en cualquier orden
        # En PostgreSQL usamos TRUNCATE ... CASCADE
        print("  [1/3] Eliminando todos los datos (CASCADE)...")
        conn.execute(text("TRUNCATE TABLE saas_tenants CASCADE;"))
        conn.execute(text("TRUNCATE TABLE saas_planes CASCADE;"))
        conn.execute(text("TRUNCATE TABLE jarvis_profiles CASCADE;"))
        conn.execute(text("TRUNCATE TABLE system_settings CASCADE;"))
        conn.execute(text("TRUNCATE TABLE ai_usage_stats CASCADE;"))
        conn.commit()
        print("        ✓ Tablas vaciadas.")

    db = SessionLocal()
    try:
        print("  [2/3] Creando plan base y superadmin...")

        # Plan base
        plan = SaaSPlan(
            nombre_plan="Plan Starter",
            permite_iot=True,
            permite_mikrotik=True,
            permite_telegram=True,
            permite_whatsapp=True,
        )
        db.add(plan)
        db.flush()

        # Tenant del superadmin
        tenant = Tenant(
            nombre_organizacion=SUPERADMIN["nombre_organizacion"],
            nombre_contacto=SUPERADMIN["nombre_contacto"],
            telefono=SUPERADMIN["telefono"],
            id_plan=plan.id_plan,
            ai_provider="gemini",
            ai_model="gemini-1.5-flash",
        )
        db.add(tenant)
        db.flush()

        # Usuario superadmin
        superadmin = Usuario(
            id_tenant=tenant.id_tenant,
            email=SUPERADMIN["email"],
            password_hash=hash_password(SUPERADMIN["password"]),
            rol=ROL_SUPERADMIN,
            is_superadmin=True,
            active_profile_ids=[],
            tokens_consumidos=0,
        )
        db.add(superadmin)
        db.commit()

        print(f"        ✓ SuperAdmin creado: {superadmin.email}")
        print(f"        ✓ Tenant creado: {tenant.nombre_organizacion} (id={tenant.id_tenant})")
        print(f"        ✓ Plan creado: {plan.nombre_plan} (id={plan.id_plan})")

        print("  [3/3] Insertando perfiles JARVIS por defecto...")
        from backend.seed_default_profiles import main as seed_profiles
        seed_profiles()
        print("        ✓ Perfiles insertados.")

    except Exception as e:
        db.rollback()
        print(f"\n  ❌ Error durante el reset: {e}")
        raise
    finally:
        db.close()

    print("\n" + "=" * 60)
    print("  ✅ RESET COMPLETADO EXITOSAMENTE")
    print(f"  Email   : {SUPERADMIN['email']}")
    print(f"  Password: {SUPERADMIN['password']}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    reset()
