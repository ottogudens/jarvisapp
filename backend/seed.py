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
        # HACK: Migración manual temporal para agregar la columna faltante
        from sqlalchemy import text
        try:
            db.execute(text("ALTER TABLE saas_planes ADD COLUMN IF NOT EXISTS permite_inspeccion BOOLEAN DEFAULT FALSE;"))
            db.execute(text("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS rol VARCHAR(20) DEFAULT 'cliente';"))
            db.execute(text("UPDATE usuarios SET rol = 'superadmin' WHERE is_superadmin = TRUE;"))
            db.commit()
            print("Migración: Estructura de BD validada (permite_inspeccion, rol).")
        except Exception as e:
            db.rollback()
            print(f"Nota de migración: {e}")

        # 1. Crear SaaS Plan Base
        plan = db.query(SaaSPlan).filter_by(nombre_plan="Plan Starter").first()
        if not plan:
            plan = SaaSPlan(nombre_plan="Plan Starter")
            db.add(plan)
            db.commit()
            db.refresh(plan)
            print(f"Creado SaaSPlan: {plan.nombre_plan}")
        else:
            print("SaaSPlan 'Plan Starter' ya existe.")

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
    finally:
        db.close()

if __name__ == "__main__":
    seed_db()
