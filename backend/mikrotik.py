from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List

from backend.database import get_db
from backend.models import MikrotikRouter
from backend.auth import obtener_usuario_actual
from backend.crypto_utils import encrypt_secret

router = APIRouter(prefix="/v1/mikrotik", tags=["MikroTik"])

class RouterCreate(BaseModel):
    nombre: str
    ip_address: str
    api_port: int = 443
    username: str
    password: str

class RouterUpdate(BaseModel):
    nombre: str | None = None
    ip_address: str | None = None
    api_port: int | None = None
    username: str | None = None
    password: str | None = None

class RouterResponse(BaseModel):
    id_router: int
    nombre: str
    ip_address: str
    api_port: int
    username: str
    is_connected: bool = False
    last_error: str | None = None
    
    class Config:
        from_attributes = True

@router.get("/routers", response_model=List[RouterResponse])
def listar_routers(usuario: dict = Depends(obtener_usuario_actual), db: Session = Depends(get_db)):
    from backend.models import Usuario
    user = db.query(Usuario).filter(Usuario.id_usuario == usuario['id_usuario']).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
    routers = db.query(MikrotikRouter).filter(MikrotikRouter.id_tenant == user.id_tenant).all()
    return routers

@router.post("/routers", response_model=RouterResponse)
def crear_router(data: RouterCreate, usuario: dict = Depends(obtener_usuario_actual), db: Session = Depends(get_db)):
    from backend.models import Usuario
    user = db.query(Usuario).filter(Usuario.id_usuario == usuario['id_usuario']).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
    nuevo_router = MikrotikRouter(
        id_tenant=user.id_tenant,
        nombre=data.nombre,
        ip_address=data.ip_address,
        api_port=data.api_port,
        username=data.username,
        password=encrypt_secret(data.password)
    )
    db.add(nuevo_router)
    db.commit()
    db.refresh(nuevo_router)
    return nuevo_router

@router.put("/routers/{id_router}", response_model=RouterResponse)
def actualizar_router(id_router: int, data: RouterUpdate, usuario: dict = Depends(obtener_usuario_actual), db: Session = Depends(get_db)):
    from backend.models import Usuario
    user = db.query(Usuario).filter(Usuario.id_usuario == usuario['id_usuario']).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
    router_db = db.query(MikrotikRouter).filter(
        MikrotikRouter.id_router == id_router,
        MikrotikRouter.id_tenant == user.id_tenant
    ).first()
    
    if not router_db:
        raise HTTPException(status_code=404, detail="Router no encontrado")
        
    if data.nombre is not None:
        router_db.nombre = data.nombre
    if data.ip_address is not None:
        router_db.ip_address = data.ip_address
    if data.api_port is not None:
        router_db.api_port = data.api_port
    if data.username is not None:
        router_db.username = data.username
    if data.password is not None and data.password != "":
        router_db.password = encrypt_secret(data.password)
        
    db.commit()
    db.refresh(router_db)
    return router_db

@router.delete("/routers/{id_router}")
def eliminar_router(id_router: int, usuario: dict = Depends(obtener_usuario_actual), db: Session = Depends(get_db)):
    from backend.models import Usuario
    user = db.query(Usuario).filter(Usuario.id_usuario == usuario['id_usuario']).first()
    
    router_db = db.query(MikrotikRouter).filter(
        MikrotikRouter.id_router == id_router,
        MikrotikRouter.id_tenant == user.id_tenant
    ).first()
    
    if not router_db:
        raise HTTPException(status_code=404, detail="Router no encontrado")
        
    db.delete(router_db)
    db.commit()
    return {"message": "Router eliminado correctamente"}

@router.post("/routers/{id_router}/connect")
def connect_router(id_router: int, usuario: dict = Depends(obtener_usuario_actual), db: Session = Depends(get_db)):
    from backend.models import Usuario
    from backend.mikrotik_service import MikrotikService
    user = db.query(Usuario).filter(Usuario.id_usuario == usuario['id_usuario']).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
    router_obj = db.query(MikrotikRouter).filter(MikrotikRouter.id_router == id_router, MikrotikRouter.id_tenant == user.id_tenant).first()
    if not router_obj:
        raise HTTPException(status_code=404, detail="Router no encontrado")

    try:
        from backend.crypto_utils import decrypt_secret
        service = MikrotikService(router_obj.ip_address, router_obj.username, decrypt_secret(router_obj.password), router_obj.api_port)
        response = service._request('GET', '/system/identity')
        if 'error' in response:
            router_obj.is_connected = False
            router_obj.last_error = str(response['error'])[:255]
        else:
            router_obj.is_connected = True
            router_obj.last_error = None
    except Exception as e:
        router_obj.is_connected = False
        router_obj.last_error = str(e)[:255]
    
    db.commit()
    return {"message": "Prueba de conexión completada", "is_connected": router_obj.is_connected, "last_error": router_obj.last_error}

@router.post("/routers/{id_router}/disconnect")
def disconnect_router(id_router: int, usuario: dict = Depends(obtener_usuario_actual), db: Session = Depends(get_db)):
    from backend.models import Usuario
    user = db.query(Usuario).filter(Usuario.id_usuario == usuario['id_usuario']).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
    router_obj = db.query(MikrotikRouter).filter(MikrotikRouter.id_router == id_router, MikrotikRouter.id_tenant == user.id_tenant).first()
    if not router_obj:
        raise HTTPException(status_code=404, detail="Router no encontrado")

    router_obj.is_connected = False
    router_obj.last_error = None
    db.commit()
    return {"message": "Router desconectado"}
