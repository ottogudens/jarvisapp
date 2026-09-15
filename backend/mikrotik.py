from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List

from backend.database import get_db
from backend.models import MikrotikRouter
from backend.auth import obtener_usuario_actual

router = APIRouter(prefix="/v1/mikrotik", tags=["MikroTik"])

class RouterCreate(BaseModel):
    nombre: str
    ip_address: str
    api_port: int = 443
    username: str
    password: str

class RouterResponse(BaseModel):
    id_router: int
    nombre: str
    ip_address: str
    api_port: int
    username: str
    
    class Config:
        orm_mode = True

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
        password=data.password
    )
    db.add(nuevo_router)
    db.commit()
    db.refresh(nuevo_router)
    return nuevo_router

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
