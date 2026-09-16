from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from pydantic import BaseModel, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from backend.database import get_db
from backend.models import Usuario, Tenant, SaaSPlan, SystemSettings, AIUsageStats
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

class JarvisProfileSchema(BaseModel):
    id_perfil: Optional[int] = None
    nombre: str
    instrucciones_base: str

class TenantProfileSchema(BaseModel):
    id_perfil: int
    nombre: str
    instrucciones_extra: str

class TenantDetailSchema(BaseModel):
    """Schema enriquecido para mostrar clientes con info del usuario principal."""
    id_tenant: int
    nombre_organizacion: str
    nombre_contacto: Optional[str] = None
    telefono: Optional[str] = None
    id_plan: int
    nombre_plan: str
    ai_provider: str
    ai_model: str
    email_admin: str
    tokens_consumidos: int
    perfiles: List[TenantProfileSchema] = []

class TenantCreateSchema(BaseModel):
    nombre_organizacion: str
    nombre_contacto: Optional[str] = None
    telefono: Optional[str] = None
    email: str
    password: Optional[str] = None
    id_plan: int
    ai_provider: str = "gemini"
    ai_model: str = "gemini-3.6-flash"
    perfiles_ids: List[int] = []

class TenantUpdateSchema(BaseModel):
    nombre_organizacion: Optional[str] = None
    nombre_contacto: Optional[str] = None
    telefono: Optional[str] = None
    id_plan: Optional[int] = None
    ai_provider: Optional[str] = None
    ai_model: Optional[str] = None
    perfiles_ids: Optional[List[int]] = None


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

# --- Endpoints Configuraciones IA ---
class AIKeysSchema(BaseModel):
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    deepseek_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None

@router.get("/ai-keys", response_model=AIKeysSchema)
def get_ai_keys(usuario: dict = Depends(requiere_superadmin), db: Session = Depends(get_db)):
    keys = db.query(SystemSettings).filter(SystemSettings.key.in_(["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "DEEPSEEK_API_KEY", "GEMINI_API_KEY"])).all()
    result = {}
    for k in keys:
        result[k.key.lower()] = k.value
    return AIKeysSchema(**result)

@router.post("/ai-keys")
def save_ai_keys(keys: AIKeysSchema, usuario: dict = Depends(requiere_superadmin), db: Session = Depends(get_db)):
    def update_or_create(key_name: str, value: str):
        if not value: return
        setting = db.query(SystemSettings).filter(SystemSettings.key == key_name).first()
        if setting:
            setting.value = value
        else:
            db.add(SystemSettings(key=key_name, value=value))
            
    update_or_create("OPENAI_API_KEY", keys.openai_api_key)
    update_or_create("ANTHROPIC_API_KEY", keys.anthropic_api_key)
    update_or_create("DEEPSEEK_API_KEY", keys.deepseek_api_key)
    update_or_create("GEMINI_API_KEY", keys.gemini_api_key)
    db.commit()
    return {"message": "Claves actualizadas exitosamente"}

class AITestRequest(BaseModel):
    provider: str
    api_key: str

@router.post("/ai-keys/test")
def test_ai_key(data: AITestRequest, usuario: dict = Depends(requiere_superadmin)):
    import litellm
    import os
    
    provider = data.provider.lower()
    
    if provider == "gemini":
        os.environ["GEMINI_API_KEY"] = data.api_key
        model = "gemini/gemini-1.5-flash"
    elif provider == "openai":
        os.environ["OPENAI_API_KEY"] = data.api_key
        model = "gpt-3.5-turbo"
    elif provider == "anthropic":
        os.environ["ANTHROPIC_API_KEY"] = data.api_key
        model = "claude-3-haiku-20240307"
    elif provider == "deepseek":
        os.environ["DEEPSEEK_API_KEY"] = data.api_key
        model = "deepseek/deepseek-chat"
    else:
        raise HTTPException(status_code=400, detail="Proveedor no soportado")
        
    try:
        response = litellm.completion(
            model=model,
            messages=[{"role": "user", "content": "Test"}],
            max_tokens=5
        )
        if response and response.choices:
            return {"message": "Clave válida"}
        raise HTTPException(status_code=400, detail="Sin respuesta")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/ai-stats")
def get_ai_stats(usuario: dict = Depends(requiere_superadmin), db: Session = Depends(get_db)):
    # Agrupar uso por proveedor
    provider_stats = db.query(
        AIUsageStats.proveedor,
        func.sum(AIUsageStats.tokens_consumidos).label("tokens"),
        func.sum(AIUsageStats.solicitudes_realizadas).label("requests")
    ).group_by(AIUsageStats.proveedor).all()
    
    # Agrupar uso por tenant (Top 5)
    tenant_stats = db.query(
        Tenant.nombre_organizacion,
        AIUsageStats.proveedor,
        func.sum(AIUsageStats.tokens_consumidos).label("tokens")
    ).join(Tenant, Tenant.id_tenant == AIUsageStats.id_tenant)\
     .group_by(Tenant.nombre_organizacion, AIUsageStats.proveedor)\
     .order_by(desc("tokens")).limit(10).all()

    return {
        "providers": [{"provider": p.proveedor, "tokens": p.tokens, "requests": p.requests} for p in provider_stats],
        "tenants": [{"tenant": t.nombre_organizacion, "provider": t.proveedor, "tokens": t.tokens} for t in tenant_stats]
    }

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

# ============================================================
# Endpoints Perfiles JARVIS
# ============================================================
@router.get("/profiles", response_model=List[JarvisProfileSchema])
def get_profiles(usuario: dict = Depends(requiere_superadmin), db: Session = Depends(get_db)):
    from backend.models import JarvisProfile
    return db.query(JarvisProfile).all()

@router.post("/profiles", response_model=JarvisProfileSchema)
def create_profile(data: JarvisProfileSchema, usuario: dict = Depends(requiere_superadmin), db: Session = Depends(get_db)):
    from backend.models import JarvisProfile
    nuevo = JarvisProfile(nombre=data.nombre, instrucciones_base=data.instrucciones_base)
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return nuevo

@router.put("/profiles/{id_perfil}", response_model=JarvisProfileSchema)
def update_profile(id_perfil: int, data: JarvisProfileSchema, usuario: dict = Depends(requiere_superadmin), db: Session = Depends(get_db)):
    from backend.models import JarvisProfile
    perfil = db.query(JarvisProfile).filter(JarvisProfile.id_perfil == id_perfil).first()
    if not perfil: raise HTTPException(status_code=404, detail="Perfil no encontrado")
    perfil.nombre = data.nombre
    perfil.instrucciones_base = data.instrucciones_base
    db.commit()
    db.refresh(perfil)
    return perfil

@router.delete("/profiles/{id_perfil}")
def delete_profile(id_perfil: int, usuario: dict = Depends(requiere_superadmin), db: Session = Depends(get_db)):
    from backend.models import JarvisProfile
    perfil = db.query(JarvisProfile).filter(JarvisProfile.id_perfil == id_perfil).first()
    if not perfil: raise HTTPException(status_code=404, detail="Perfil no encontrado")
    db.delete(perfil)
    db.commit()
    return {"message": "Perfil eliminado"}

# --- Endpoints Tenants (CRUD Completo) ---

@router.get("/tenants", response_model=List[TenantDetailSchema])
def get_tenants(
    usuario: dict = Depends(requiere_superadmin),
    db: Session = Depends(get_db)
):
    from backend.models import TenantProfile
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
        
        # Obtener perfiles asignados
        tp_list = db.query(TenantProfile).filter(TenantProfile.id_tenant == t.id_tenant).all()
        perfiles_data = [{"id_perfil": tp.perfil.id_perfil, "nombre": tp.perfil.nombre, "instrucciones_extra": tp.instrucciones_extra} for tp in tp_list]

        result.append(TenantDetailSchema(
            id_tenant=t.id_tenant,
            nombre_organizacion=t.nombre_organizacion,
            nombre_contacto=t.nombre_contacto,
            telefono=t.telefono,
            id_plan=t.id_plan,
            nombre_plan=plan.nombre_plan if plan else "Sin plan",
            ai_provider=t.ai_provider,
            ai_model=t.ai_model,
            email_admin=user.email if user else "Sin usuario",
            tokens_consumidos=total_tokens,
            perfiles=perfiles_data
        ))
    return result


@router.post("/tenants", response_model=TenantDetailSchema)
def create_tenant(
    data: TenantCreateSchema,
    usuario: dict = Depends(requiere_superadmin),
    db: Session = Depends(get_db)
):
    from backend.models import TenantProfile
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
        nombre_contacto=data.nombre_contacto,
        telefono=data.telefono,
        id_plan=data.id_plan,
        ai_provider=data.ai_provider,
        ai_model=data.ai_model,
    )
    db.add(new_tenant)
    db.flush()  # Para obtener el id_tenant
    
    # Asignar perfiles
    for p_id in data.perfiles_ids:
        db.add(TenantProfile(id_tenant=new_tenant.id_tenant, id_perfil=p_id))

    # Crear usuario principal del tenant
    pwd = data.password if data.password else "Admin123!"
    new_user = Usuario(
        id_tenant=new_tenant.id_tenant,
        email=data.email,
        password_hash=hash_password(pwd),
    )
    if data.perfiles_ids:
        new_user.active_profile_id = data.perfiles_ids[0]
        
    db.add(new_user)
    db.commit()
    
    tenants = get_tenants(usuario, db)
    return [t for t in tenants if t.id_tenant == new_tenant.id_tenant][0]

@router.put("/tenants/{id_tenant}", response_model=TenantDetailSchema)
def update_tenant(
    id_tenant: int,
    update_data: TenantUpdateSchema,
    usuario: dict = Depends(requiere_superadmin),
    db: Session = Depends(get_db)
):
    from backend.models import TenantProfile
    """Actualiza la informacion de un cliente."""
    db_tenant = db.query(Tenant).filter(Tenant.id_tenant == id_tenant).first()
    if not db_tenant:
        raise HTTPException(status_code=404, detail="Tenant no encontrado")
    
    if update_data.nombre_organizacion is not None:
        db_tenant.nombre_organizacion = update_data.nombre_organizacion
    if update_data.nombre_contacto is not None:
        db_tenant.nombre_contacto = update_data.nombre_contacto
    if update_data.telefono is not None:
        db_tenant.telefono = update_data.telefono
    if update_data.ai_provider is not None:
        db_tenant.ai_provider = update_data.ai_provider
    if update_data.ai_model is not None:
        db_tenant.ai_model = update_data.ai_model
    if update_data.id_plan is not None:
        plan = db.query(SaaSPlan).filter(SaaSPlan.id_plan == update_data.id_plan).first()
        if not plan: raise HTTPException(status_code=404, detail="Plan no encontrado")
        db_tenant.id_plan = update_data.id_plan
        
    if update_data.perfiles_ids is not None:
        # Reemplazar perfiles actuales
        db.query(TenantProfile).filter(TenantProfile.id_tenant == id_tenant).delete()
        for p_id in update_data.perfiles_ids:
            db.add(TenantProfile(id_tenant=id_tenant, id_perfil=p_id))
    
    db.commit()
    
    tenants = get_tenants(usuario, db)
    return [t for t in tenants if t.id_tenant == id_tenant][0]

class UpdateInstruccionesSchema(BaseModel):
    id_perfil: int
    instrucciones_extra: str

@router.put("/tenant/profiles", response_model=dict)
def update_tenant_profile_instructions(
    data: UpdateInstruccionesSchema,
    usuario: dict = Depends(obtener_usuario_actual),
    db: Session = Depends(get_db)
):
    from backend.models import TenantProfile
    tp = db.query(TenantProfile).filter(
        TenantProfile.id_tenant == usuario["id_tenant"],
        TenantProfile.id_perfil == data.id_perfil
    ).first()
    
    if not tp:
        raise HTTPException(status_code=404, detail="Perfil no asignado al cliente")
        
    tp.instrucciones_extra = data.instrucciones_extra
    db.commit()
    return {"message": "Instrucciones actualizadas"}


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
