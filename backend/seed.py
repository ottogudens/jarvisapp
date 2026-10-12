import os
import sys
from dotenv import load_dotenv
from sqlalchemy.orm import Session

# Agregar el root del proyecto al PYTHONPATH
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Cargar variables de entorno
load_dotenv(os.path.join(project_root, ".env"))

from backend.database import engine, get_db
from backend.models import Base, SaaSPlan, Tenant, Usuario, ROL_SUPERADMIN
from backend.auth import hash_password

def seed_db():
    print("Iniciando Seed Limpio de Base de Datos (Solo SuperAdmin)...")
    
    # Asegurarnos de que el esquema existe si no corrimos alembic
    Base.metadata.create_all(bind=engine)
    
    db: Session = next(get_db())
    
    try:
        # 1. Catálogo comercial. Se actualizan solo estos planes de sistema;
        # los planes personalizados creados por administración no se tocan.
        catalog = {
            "Bonso Inicial": dict(precio_mensual=29990, tokens_mensuales=100000, max_documentos=100, almacenamiento_bytes=2 * 1024**3, max_upload_bytes=15 * 1024**2, permite_telegram=True),
            "Bonso Profesional": dict(precio_mensual=79990, tokens_mensuales=500000, max_documentos=1000, almacenamiento_bytes=10 * 1024**3, max_upload_bytes=30 * 1024**2, permite_telegram=True, permite_whatsapp=True, permite_google_workspace=True, permite_facebook=True, permite_instagram=True),
            "Bonso Empresa": dict(precio_mensual=149990, tokens_mensuales=2000000, max_documentos=5000, almacenamiento_bytes=50 * 1024**3, max_upload_bytes=100 * 1024**2, permite_telegram=True, permite_whatsapp=True, permite_google_workspace=True, permite_facebook=True, permite_instagram=True, permite_tiktok=True, permite_iot=True, permite_mikrotik=True),
        }
        plans = {}
        for name, values in catalog.items():
            plan = db.query(SaaSPlan).filter_by(nombre_plan=name).first()
            if not plan:
                plan = SaaSPlan(nombre_plan=name, moneda="CLP")
                db.add(plan)
            for key, value in values.items(): setattr(plan, key, value)
            plans[name] = plan
        db.commit()
        plan = plans["Bonso Empresa"]
        print("Catálogo Bonso Inicial, Profesional y Empresa disponible.")

        # 2. Crear Tenant Base para el sistema
        tenant = db.query(Tenant).filter_by(nombre_organizacion="Skale IA").first()
        if not tenant:
            tenant = Tenant(
                nombre_organizacion="Skale IA",
                nombre_contacto="Administrador del Sistema",
                id_plan=plan.id_plan,
            )
            db.add(tenant)
            db.commit()
            db.refresh(tenant)
            print(f"Creado Tenant: {tenant.nombre_organizacion}")
        else:
            print("Tenant 'Skale IA' ya existe.")

        # 3. Crear Usuario SuperAdmin
        admin_email = "admin@skale.cl"
        usuario = db.query(Usuario).filter_by(email=admin_email).first()
        if not usuario:
            usuario = Usuario(
                id_tenant=tenant.id_tenant,
                email=admin_email,
                password_hash=hash_password("Admin123!"),
                rol=ROL_SUPERADMIN,
                is_superadmin=True
            )
            db.add(usuario)
            db.commit()
            db.refresh(usuario)
            print(f"Creado Usuario SuperAdmin: {usuario.email}")
        else:
            print("Usuario SuperAdmin ya existe.")
            # Asegurar que tenga el rol y permisos correctos aunque ya exista
            usuario.rol = ROL_SUPERADMIN
            usuario.is_superadmin = True
            db.commit()

        print("Seed completado exitosamente.")

    except Exception as e:
        db.rollback()
        print(f"Error durante el seed: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed_db()
