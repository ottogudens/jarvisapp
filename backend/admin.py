from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel, ConfigDict
from typing import List, Optional

from backend.database import get_db
from backend.models import Usuario, Tenant, SaaSPlan
from backend.auth import obtener_usuario_actual

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

class TenantSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_tenant: int
    nombre_organizacion: str
    id_plan: int

class TenantUpdateSchema(BaseModel):
    id_plan: int


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


# --- Endpoints Tenants ---
@router.get("/tenants", response_model=List[TenantSchema])
def get_tenants(
    usuario: dict = Depends(requiere_superadmin),
    db: Session = Depends(get_db)
):
    tenants = db.query(Tenant).all()
    return tenants

@router.put("/tenants/{id_tenant}", response_model=TenantSchema)
def update_tenant(
    id_tenant: int,
    update_data: TenantUpdateSchema,
    usuario: dict = Depends(requiere_superadmin),
    db: Session = Depends(get_db)
):
    db_tenant = db.query(Tenant).filter(Tenant.id_tenant == id_tenant).first()
    if not db_tenant:
        raise HTTPException(status_code=404, detail="Tenant no encontrado")
    
    db_tenant.id_plan = update_data.id_plan
    db.commit()
    db.refresh(db_tenant)
    return db_tenant
