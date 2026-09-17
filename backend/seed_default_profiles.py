"""
Inserta (o actualiza) los perfiles JARVIS por defecto en la base de datos.

Uso:
    python -m backend.seed_default_profiles

Es seguro correrlo varias veces: si el perfil ya existe (por `nombre`, que es
unique en el modelo), actualiza `instrucciones_base`; si no existe, lo crea.
No toca `TenantProfile` — asignar estos perfiles a un tenant se sigue haciendo
desde el admin panel (PUT /v1/admin/tenants/{id}) como siempre.
"""
from backend.database import SessionLocal
from backend.models import JarvisProfile
from backend.perfiles_default import PERFILES_DEFAULT


def main():
    with SessionLocal() as db:
        creados, actualizados = 0, 0
        for data in PERFILES_DEFAULT:
            existente = db.query(JarvisProfile).filter(
                JarvisProfile.nombre == data["nombre"]
            ).first()
            if existente:
                if existente.instrucciones_base != data["instrucciones_base"]:
                    existente.instrucciones_base = data["instrucciones_base"]
                    actualizados += 1
            else:
                db.add(JarvisProfile(
                    nombre=data["nombre"],
                    instrucciones_base=data["instrucciones_base"],
                ))
                creados += 1
        db.commit()
        print(f"Perfiles creados: {creados} | actualizados: {actualizados} | total definidos: {len(PERFILES_DEFAULT)}")


if __name__ == "__main__":
    main()
