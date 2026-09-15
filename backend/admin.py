from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel, ConfigDict
from typing import List, Optional

from backend.database import get_db
from backend.models import Usuario, Tenant, SaaSPlan
from backend.auth import obtener_usuario_actual, hash_password

router = APIRouter(prefix="/v1/admin", tags=["Administrador"])

# --- Dependencia ---
def requiere_superadmin(usuario: dict = Depends(obtener_usuario_actual)):
    if not usuario.get("is_superadmin", False):
        raise HTTPException(status_code=403, detail="Acceso denegado. Requiere privilegios de Superadmin.")
    return usuario


# --- Schemas ---
class DashboardStats(BaseModel):
    total_clientes: int
    total_agentes: int
    tokens_consumidos: int

class SaaSPlanSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_plan: Optional[int] = None
    nombre_plan: str
    permite_erp: bool
    permite_inspeccion: bool
    permite_iot: bool
    permite_mikrotik: bool

class TenantDetailSchema(BaseModel):
    """Schema enriquecido para mostrar clientes con info del usuario principal."""
    id_tenant: int
    nombre_organizacion: str
    id_plan: int
    nombre_plan: str
    email_admin: str
    perfil_jarvis: str
    tokens_consumidos: int

class TenantCreateSchema(BaseModel):
    nombre_organizacion: str
    email: str
    password: str
    perfil_jarvis: str = "Mecanico"
    id_plan: int

class TenantUpdateSchema(BaseModel):
    nombre_organizacion: Optional[str] = None
    id_plan: Optional[int] = None


# --- Endpoints Dashboard ---
@router.get("/dashboard", response_model=DashboardStats)
def get_dashboard(
    usuario: dict = Depends(requiere_superadmin),
    db: Session = Depends(get_db)
):
    total_clientes = db.query(Tenant).count()
    total_agentes = db.query(Usuario).count()
    tokens = db.query(func.sum(Usuario.tokens_consumidos)).scalar() or 0

    return DashboardStats(
        total_clientes=total_clientes,
        total_agentes=total_agentes,
        tokens_consumidos=tokens
    )

# --- Endpoints Planes ---
@router.get("/plans", response_model=List[SaaSPlanSchema])
def get_plans(
    usuario: dict = Depends(requiere_superadmin),
    db: Session = Depends(get_db)
):
    planes = db.query(SaaSPlan).all()
    return planes

@router.post("/plans", response_model=SaaSPlanSchema)
def create_plan(
    plan: SaaSPlanSchema,
    usuario: dict = Depends(requiere_superadmin),
    db: Session = Depends(get_db)
):
    db_plan = SaaSPlan(
        nombre_plan=plan.nombre_plan,
        permite_erp=plan.permite_erp,
        permite_inspeccion=plan.permite_inspeccion,
        permite_iot=plan.permite_iot,
        permite_mikrotik=plan.permite_mikrotik
    )
    db.add(db_plan)
    db.commit()
    db.refresh(db_plan)
    return db_plan

@router.put("/plans/{id_plan}", response_model=SaaSPlanSchema)
def update_plan(
    id_plan: int,
    plan: SaaSPlanSchema,
    usuario: dict = Depends(requiere_superadmin),
    db: Session = Depends(get_db)
):
    db_plan = db.query(SaaSPlan).filter(SaaSPlan.id_plan == id_plan).first()
    if not db_plan:
        raise HTTPException(status_code=404, detail="Plan no encontrado")
    
    db_plan.nombre_plan = plan.nombre_plan
    db_plan.permite_erp = plan.permite_erp
    db_plan.permite_inspeccion = plan.permite_inspeccion
    db_plan.permite_iot = plan.permite_iot
    db_plan.permite_mikrotik = plan.permite_mikrotik
    
    db.commit()
    db.refresh(db_plan)
    return db_plan


# --- Endpoints Tenants (CRUD Completo) ---

@router.get("/tenants", response_model=List[TenantDetailSchema])
def get_tenants(
    usuario: dict = Depends(requiere_superadmin),
    db: Session = Depends(get_db)
):
    """Lista todos los clientes con datos enriquecidos (email, plan, tokens)."""
    tenants = db.query(Tenant).all()
    result = []
    for t in tenants:
        # Buscar el primer usuario del tenant como "admin" del tenant
        user = db.query(Usuario).filter(Usuario.id_tenant == t.id_tenant).first()
        plan = db.query(SaaSPlan).filter(SaaSPlan.id_plan == t.id_plan).first()
        # Sumar tokens de todos los usuarios del tenant
        total_tokens = db.query(func.sum(Usuario.tokens_consumidos)).filter(
            Usuario.id_tenant == t.id_tenant
        ).scalar() or 0

        result.append(TenantDetailSchema(
            id_tenant=t.id_tenant,
            nombre_organizacion=t.nombre_organizacion,
            id_plan=t.id_plan,
            nombre_plan=plan.nombre_plan if plan else "Sin plan",
            email_admin=user.email if user else "Sin usuario",
            perfil_jarvis=user.perfil_jarvis if user else "N/A",
            tokens_consumidos=total_tokens,
        ))
    return result


@router.post("/tenants", response_model=TenantDetailSchema)
def create_tenant(
    data: TenantCreateSchema,
    usuario: dict = Depends(requiere_superadmin),
    db: Session = Depends(get_db)
):
    """Crea un nuevo cliente (tenant) junto con su usuario administrador."""
    # Validar que el plan existe
    plan = db.query(SaaSPlan).filter(SaaSPlan.id_plan == data.id_plan).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan no encontrado")

    # Validar que el email no exista
    existing = db.query(Usuario).filter(Usuario.email == data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="El email ya está en uso por otro usuario")

    # Crear tenant
    new_tenant = Tenant(
        nombre_organizacion=data.nombre_organizacion,
        id_plan=data.id_plan,
    )
    db.add(new_tenant)
    db.flush()  # Para obtener el id_tenant

    # Crear usuario principal del tenant
    new_user = Usuario(
        id_tenant=new_tenant.id_tenant,
        email=data.email,
        password_hash=hash_password(data.password),
        perfil_jarvis=data.perfil_jarvis,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_tenant)
    db.refresh(new_user)

    return TenantDetailSchema(
        id_tenant=new_tenant.id_tenant,
        nombre_organizacion=new_tenant.nombre_organizacion,
        id_plan=new_tenant.id_plan,
        nombre_plan=plan.nombre_plan,
        email_admin=new_user.email,
        perfil_jarvis=new_user.perfil_jarvis,
        tokens_consumidos=0,
    )


@router.put("/tenants/{id_tenant}", response_model=TenantDetailSchema)
def update_tenant(
    id_tenant: int,
    update_data: TenantUpdateSchema,
    usuario: dict = Depends(requiere_superadmin),
    db: Session = Depends(get_db)
):
    """Actualiza el nombre y/o plan de un cliente."""
    db_tenant = db.query(Tenant).filter(Tenant.id_tenant == id_tenant).first()
    if not db_tenant:
        raise HTTPException(status_code=404, detail="Tenant no encontrado")
    
    if update_data.nombre_organizacion is not None:
        db_tenant.nombre_organizacion = update_data.nombre_organizacion
    if update_data.id_plan is not None:
        plan = db.query(SaaSPlan).filter(SaaSPlan.id_plan == update_data.id_plan).first()
        if not plan:
            raise HTTPException(status_code=404, detail="Plan no encontrado")
        db_tenant.id_plan = update_data.id_plan
    
    db.commit()
    db.refresh(db_tenant)

    user = db.query(Usuario).filter(Usuario.id_tenant == id_tenant).first()
    plan = db.query(SaaSPlan).filter(SaaSPlan.id_plan == db_tenant.id_plan).first()
    total_tokens = db.query(func.sum(Usuario.tokens_consumidos)).filter(
        Usuario.id_tenant == id_tenant
    ).scalar() or 0

    return TenantDetailSchema(
        id_tenant=db_tenant.id_tenant,
        nombre_organizacion=db_tenant.nombre_organizacion,
        id_plan=db_tenant.id_plan,
        nombre_plan=plan.nombre_plan if plan else "Sin plan",
        email_admin=user.email if user else "Sin usuario",
        perfil_jarvis=user.perfil_jarvis if user else "N/A",
        tokens_consumidos=total_tokens,
    )


@router.delete("/tenants/{id_tenant}")
def delete_tenant(
    id_tenant: int,
    usuario: dict = Depends(requiere_superadmin),
    db: Session = Depends(get_db)
):
    """Elimina un cliente y todos sus datos asociados (cascade)."""
    db_tenant = db.query(Tenant).filter(Tenant.id_tenant == id_tenant).first()
    if not db_tenant:
        raise HTTPException(status_code=404, detail="Tenant no encontrado")
    
    # No permitir eliminar el tenant del superadmin
    superadmin_user = db.query(Usuario).filter(
        Usuario.id_tenant == id_tenant,
        Usuario.is_superadmin == True
    ).first()
    if superadmin_user:
        raise HTTPException(status_code=400, detail="No se puede eliminar el tenant del SuperAdmin")

    db.delete(db_tenant)
    db.commit()
    return {"message": f"Cliente '{db_tenant.nombre_organizacion}' eliminado correctamente"}
