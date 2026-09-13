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
from backend.models import Base, SaaSPlan, Tenant, Usuario, Cliente, Vehiculo, OrdenTrabajo
from backend.auth import hash_password

def seed_db():
    print("Iniciando Seed de Base de Datos...")
    
    # Asegurarnos de que el esquema existe si no corrimos alembic
    Base.metadata.create_all(bind=engine)
    
    db: Session = next(get_db())
    
    try:
        # 1. Crear SaaS Plan
        plan = db.query(SaaSPlan).filter_by(nombre_plan="Plan Pro Auto").first()
        if not plan:
            plan = SaaSPlan(nombre_plan="Plan Pro Auto", permite_erp=True)
            db.add(plan)
            db.commit()
            db.refresh(plan)
            print(f"Creado SaaSPlan: {plan.nombre_plan}")
        else:
            print("SaaSPlan ya existe.")

        # 2. Crear Tenant
        tenant = db.query(Tenant).filter_by(nombre_organizacion="Taller Los Hermanos").first()
        if not tenant:
            tenant = Tenant(
                nombre_organizacion="Taller Los Hermanos",
                id_plan=plan.id_plan,
            )
            db.add(tenant)
            db.commit()
            db.refresh(tenant)
            print(f"Creado Tenant: {tenant.nombre_organizacion}")
        else:
            print("Tenant ya existe.")

        # 3. Crear Usuario (Mecánico)
        usuario = db.query(Usuario).filter_by(email="mecanico@loshermanos.com").first()
        if not usuario:
            usuario = Usuario(
                id_tenant=tenant.id_tenant,
                email="mecanico@loshermanos.com",
                password_hash=hash_password("admin123"),
                perfil_jarvis="Mecanico"
            )
            db.add(usuario)
            db.commit()
            db.refresh(usuario)
            print(f"Creado Usuario: {usuario.email}")
        else:
            print("Usuario ya existe.")

        # 4. Crear Cliente y Vehículo
        cliente = db.query(Cliente).filter_by(email="juan.perez@email.com").first()
        if not cliente:
            cliente = Cliente(
                id_tenant=tenant.id_tenant,
                rut="12345678-9",
                nombre="Juan Perez",
                telefono="555-1234",
                email="juan.perez@email.com"
            )
            db.add(cliente)
            db.commit()
            db.refresh(cliente)
            print(f"Creado Cliente: {cliente.nombre}")
        else:
            print("Cliente ya existe.")

        vehiculo = db.query(Vehiculo).filter_by(patente="AB123CD").first()
        if not vehiculo:
            vehiculo = Vehiculo(
                id_tenant=tenant.id_tenant,
                id_cliente=cliente.id_cliente,
                patente="AB123CD",
                marca="Toyota",
                modelo="Corolla"
            )
            db.add(vehiculo)
            db.commit()
            db.refresh(vehiculo)
            print(f"Creado Vehiculo: {vehiculo.marca} {vehiculo.modelo}")
        else:
            print("Vehiculo ya existe.")

        # 5. Crear Orden de Trabajo inicial
        orden = db.query(OrdenTrabajo).filter_by(id_vehiculo=vehiculo.id_vehiculo).first()
        if not orden:
            orden = OrdenTrabajo(
                id_tenant=tenant.id_tenant,
                id_vehiculo=vehiculo.id_vehiculo,
                folio_ot="OT-0001",
                estado="Recepción",
                diagnostico_ia="El cliente reporta pérdida de líquido refrigerante. Requiere revisión."
            )
            db.add(orden)
            db.commit()
            db.refresh(orden)
            print(f"Creada Orden de Trabajo: ID {orden.id_orden}")
        else:
            print("Orden de Trabajo ya existe.")
            
        # ============================================================
        # 6. Seed para perfil Inspector DGC
        # ============================================================
        
        # Plan Inspector
        plan_inspector = db.query(SaaSPlan).filter_by(nombre_plan="Plan Inspector DGC").first()
        if not plan_inspector:
            plan_inspector = SaaSPlan(nombre_plan="Plan Inspector DGC", permite_inspeccion=True)
            db.add(plan_inspector)
            db.commit()
            db.refresh(plan_inspector)
            print(f"Creado SaaSPlan: {plan_inspector.nombre_plan}")
        else:
            print("SaaSPlan Inspector ya existe.")

        # Tenant Municipalidad
        tenant_muni = db.query(Tenant).filter_by(nombre_organizacion="Municipalidad de Santiago").first()
        if not tenant_muni:
            tenant_muni = Tenant(
                nombre_organizacion="Municipalidad de Santiago",
                id_plan=plan_inspector.id_plan,
            )
            db.add(tenant_muni)
            db.commit()
            db.refresh(tenant_muni)
            print(f"Creado Tenant: {tenant_muni.nombre_organizacion}")
        else:
            print("Tenant Municipalidad ya existe.")

        # Usuario Inspector
        inspector = db.query(Usuario).filter_by(email="inspector@municipalidad.cl").first()
        if not inspector:
            inspector = Usuario(
                id_tenant=tenant_muni.id_tenant,
                email="inspector@municipalidad.cl",
                password_hash=hash_password("admin123"),
                perfil_jarvis="Inspector_DGC"
            )
            db.add(inspector)
            db.commit()
            db.refresh(inspector)
            print(f"Creado Usuario Inspector: {inspector.email}")
        else:
            print("Usuario Inspector ya existe.")

        print("Seed completado exitosamente.")

    except Exception as e:
        db.rollback()
        print(f"Error durante el seed: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_db()
