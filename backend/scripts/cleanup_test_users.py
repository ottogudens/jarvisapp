import os
import sys
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from sqlalchemy import text

# Agregar el root del proyecto al PYTHONPATH
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Cargar variables de entorno
load_dotenv(os.path.join(project_root, ".env"))

from backend.database import get_db
from backend.models import Usuario, Tenant, Cliente, Vehiculo, OrdenTrabajo

def cleanup_test_data():
    """Elimina los tenants y usuarios de prueba viejos."""
    print("Iniciando limpieza de datos de prueba...")
    db: Session = next(get_db())
    
    try:
        # Tenants a borrar por su nombre de organizacion
        test_tenants = ["Taller Los Hermanos", "Municipalidad de Santiago"]
        
        tenants_db = db.query(Tenant).filter(Tenant.nombre_organizacion.in_(test_tenants)).all()
        
        if not tenants_db:
            print("No se encontraron tenants de prueba para borrar.")
        
        for t in tenants_db:
            print(f"Borrando tenant: {t.nombre_organizacion} (cascada eliminará usuarios, clientes asocidados)")
            db.delete(t)
            
        # Emails sueltos de prueba por si quedaron sin tenant
        test_emails = ["mecanico@skale.cl", "inspector@skale.cl", "mecanico@loshermanos.com", "inspector@municipalidad.cl"]
        usuarios = db.query(Usuario).filter(Usuario.email.in_(test_emails)).all()
        for u in usuarios:
            print(f"Borrando usuario suelto: {u.email}")
            db.delete(u)
            
        db.commit()
        print("Limpieza completada exitosamente.")
    except Exception as e:
        db.rollback()
        print(f"Error durante la limpieza: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    cleanup_test_data()
