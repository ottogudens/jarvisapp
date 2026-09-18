from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from pydantic import BaseModel, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime
import bcrypt

from backend.database import get_db
from backend.models import Usuario, Tenant, SaaSPlan, SystemSettings, AIUsageStats, ROL_SUPERADMIN, ROL_ADMIN, ROL_CLIENTE, ROLS_STAFF
from backend.auth import obtener_usuario_actual, hash_password, requiere_staff, requiere_superadmin

router = APIRouter(prefix="/v1/admin", tags=["Administrador"])


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
    ai_model: str = "gemini-1.5-flash"
    perfiles_ids: List[int] = []

class TenantUpdateSchema(BaseModel):
    nombre_organizacion: Optional[str] = None
    nombre_contacto: Optional[str] = None
    telefono: Optional[str] = None
    id_plan: Optional[int] = None
    ai_provider: Optional[str] = None
    ai_model: Optional[str] = None
    perfiles_ids: Optional[List[int]] = None

class UsuarioSchema(BaseModel):
    id_usuario: int
    email: str
    rol: str
    active_profile_id: Optional[int] = None

class UsuarioCreateSchema(BaseModel):
    email: str
    password: str
    rol: str = ROL_CLIENTE
    active_profile_id: Optional[int] = None

class UsuarioUpdateSchema(BaseModel):
    email: Optional[str] = None
    password: Optional[str] = None
    rol: Optional[str] = None
    active_profile_id: Optional[int] = None

# --- Endpoints Dashboard ---
@router.get("/dashboard", response_model=DashboardStats)
def get_dashboard(
    usuario: dict = Depends(requiere_staff),
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
def get_ai_keys(usuario: dict = Depends(requiere_staff), db: Session = Depends(get_db)):
    keys = db.query(SystemSettings).filter(SystemSettings.key.in_(["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "DEEPSEEK_API_KEY", "GEMINI_API_KEY"])).all()
    result = {}
    for k in keys:
        result[k.key.lower()] = k.value
    return AIKeysSchema(**result)

@router.post("/ai-keys")
def save_ai_keys(keys: AIKeysSchema, usuario: dict = Depends(requiere_staff), db: Session = Depends(get_db)):
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

# --- Endpoints Planes ---
@router.get("/plans", response_model=List[SaaSPlanSchema])
def get_plans(
    usuario: dict = Depends(requiere_staff),
    db: Session = Depends(get_db)
):
    planes = db.query(SaaSPlan).all()
    return planes

@router.post("/plans", response_model=SaaSPlanSchema)
def create_plan(
    plan: SaaSPlanSchema,
    usuario: dict = Depends(requiere_staff),
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
    usuario: dict = Depends(requiere_staff),
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
def get_profiles(usuario: dict = Depends(requiere_staff), db: Session = Depends(get_db)):
    from backend.models import JarvisProfile
    return db.query(JarvisProfile).all()

@router.post("/profiles", response_model=JarvisProfileSchema)
def create_profile(data: JarvisProfileSchema, usuario: dict = Depends(requiere_staff), db: Session = Depends(get_db)):
    from backend.models import JarvisProfile
    nuevo = JarvisProfile(nombre=data.nombre, instrucciones_base=data.instrucciones_base)
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return nuevo

@router.put("/profiles/{id_perfil}", response_model=JarvisProfileSchema)
def update_profile(id_perfil: int, data: JarvisProfileSchema, usuario: dict = Depends(requiere_staff), db: Session = Depends(get_db)):
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
    usuario: dict = Depends(requiere_staff),
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
    usuario: dict = Depends(requiere_staff),
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
        rol=ROL_CLIENTE,
        is_superadmin=False
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
    usuario: dict = Depends(requiere_staff),
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
        Usuario.rol == 'superadmin'
    ).first()
    if superadmin_user:
        raise HTTPException(status_code=400, detail="No se puede eliminar el tenant del SuperAdmin")

    db.delete(db_tenant)
    db.commit()
    return {"message": f"Cliente '{db_tenant.nombre_organizacion}' eliminado correctamente"}

# ============================================================
# Endpoints AI Stats & AI Keys
# ============================================================

@router.get("/ai-stats")
def get_ai_stats(usuario: dict = Depends(requiere_superadmin), db: Session = Depends(get_db)):
    stats = db.query(AIUsageStats).all()
    grouped_by_provider = {}
    for s in stats:
        if s.proveedor not in grouped_by_provider:
            grouped_by_provider[s.proveedor] = {"provider": s.proveedor, "tokens": 0, "requests": 0}
        grouped_by_provider[s.proveedor]["tokens"] += (s.tokens_consumidos or 0)
        grouped_by_provider[s.proveedor]["requests"] += (s.solicitudes_realizadas or 0)

    return {
        "providers": list(grouped_by_provider.values()),
        "raw": [
            {
                "id_tenant": s.id_tenant,
                "proveedor": s.proveedor,
                "tokens_consumidos": s.tokens_consumidos,
                "solicitudes_realizadas": s.solicitudes_realizadas
            } for s in stats
        ]
    }

class AIKeyTest(BaseModel):
    provider: str
    api_key: str

@router.post("/ai-keys/test")
def test_ai_key(data: AIKeyTest, usuario: dict = Depends(requiere_superadmin)):
    import litellm
    from litellm import completion
    import os
    
    provider = data.provider.lower()
    os.environ[f"{provider.upper()}_API_KEY"] = data.api_key
    
    if provider == "openai":
        model = "openai/gpt-3.5-turbo"
    elif provider == "anthropic" or provider == "claude":
        model = "anthropic/claude-3-haiku-20240307"
    elif provider == "gemini":
        model = "gemini/gemini-1.5-flash"
    elif provider == "deepseek":
        model = "deepseek/deepseek-chat"
    else:
        raise HTTPException(status_code=400, detail="Proveedor desconocido")

    try:
        response = completion(
            model=model,
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=5
        )
        return {"status": "ok", "message": "Key is valid"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ============================================================
# Endpoints Usuarios (Clientes por Tenant)
# ============================================================

@router.get("/tenants/{id_tenant}/users", response_model=List[UsuarioSchema])
def get_tenant_users(
    id_tenant: int,
    usuario: dict = Depends(requiere_staff),
    db: Session = Depends(get_db)
):
    usuarios = db.query(Usuario).filter(Usuario.id_tenant == id_tenant).all()
    return [UsuarioSchema(
        id_usuario=u.id_usuario,
        email=u.email,
        rol=u.rol,
        active_profile_id=u.active_profile_id
    ) for u in usuarios]


@router.post("/tenants/{id_tenant}/users", response_model=UsuarioSchema)
def create_tenant_user(
    id_tenant: int,
    data: UsuarioCreateSchema,
    usuario: dict = Depends(requiere_staff),
    db: Session = Depends(get_db)
):
    tenant = db.query(Tenant).filter(Tenant.id_tenant == id_tenant).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant no encontrado")

    existing = db.query(Usuario).filter(Usuario.email == data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="El email ya está en uso")

    if data.rol not in [ROL_ADMIN, ROL_CLIENTE]:
        if not (data.rol == ROL_SUPERADMIN and usuario.get("rol") == ROL_SUPERADMIN):
            raise HTTPException(status_code=400, detail="Rol inválido")

    nuevo_usuario = Usuario(
        id_tenant=id_tenant,
        email=data.email,
        password_hash=hash_password(data.password),
        rol=data.rol,
        is_superadmin=(data.rol == ROL_SUPERADMIN),
        active_profile_id=data.active_profile_id
    )
    db.add(nuevo_usuario)
    db.commit()
    db.refresh(nuevo_usuario)

    return UsuarioSchema(
        id_usuario=nuevo_usuario.id_usuario,
        email=nuevo_usuario.email,
        rol=nuevo_usuario.rol,
        active_profile_id=nuevo_usuario.active_profile_id
    )


@router.put("/tenants/{id_tenant}/users/{id_usuario}", response_model=UsuarioSchema)
def update_tenant_user(
    id_tenant: int,
    id_usuario: int,
    data: UsuarioUpdateSchema,
    usuario: dict = Depends(requiere_staff),
    db: Session = Depends(get_db)
):
    target_user = db.query(Usuario).filter(
        Usuario.id_usuario == id_usuario,
        Usuario.id_tenant == id_tenant
    ).first()

    if not target_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    # Solo un superadmin puede modificar roles de superadmin,
    # un admin no puede auto-elevarse a superadmin ni bajar a un superadmin.
    if target_user.rol == ROL_SUPERADMIN and usuario.get("rol") != ROL_SUPERADMIN:
        raise HTTPException(status_code=403, detail="No tienes permisos para modificar un SuperAdmin")

    if data.email:
        if data.email != target_user.email:
            existing = db.query(Usuario).filter(Usuario.email == data.email).first()
            if existing:
                raise HTTPException(status_code=400, detail="El email ya está en uso")
        target_user.email = data.email

    if data.password:
        target_user.password_hash = hash_password(data.password)

    if data.rol:
        if data.rol == ROL_SUPERADMIN and usuario.get("rol") != ROL_SUPERADMIN:
            raise HTTPException(status_code=403, detail="Solo un superadmin puede asignar el rol de superadmin")
        target_user.rol = data.rol
        target_user.is_superadmin = (data.rol == ROL_SUPERADMIN)

    if data.active_profile_id is not None:
        target_user.active_profile_id = data.active_profile_id

    db.commit()
    db.refresh(target_user)

    return UsuarioSchema(
        id_usuario=target_user.id_usuario,
        email=target_user.email,
        rol=target_user.rol,
        active_profile_id=target_user.active_profile_id
    )


@router.delete("/tenants/{id_tenant}/users/{id_usuario}")
def delete_tenant_user(
    id_tenant: int,
    id_usuario: int,
    usuario: dict = Depends(requiere_staff),
    db: Session = Depends(get_db)
):
    target_user = db.query(Usuario).filter(
        Usuario.id_usuario == id_usuario,
        Usuario.id_tenant == id_tenant
    ).first()

    if not target_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    # Evitar borrar admin si no soy superadmin
    if target_user.rol in ROLS_STAFF and usuario.get("rol") != ROL_SUPERADMIN:
        raise HTTPException(status_code=403, detail="No puedes eliminar a un usuario de nivel administrador")

    if target_user.id_usuario == usuario.get("id_usuario"):
        raise HTTPException(status_code=400, detail="No puedes eliminarte a ti mismo")

    db.delete(target_user)
    db.commit()
    return {"message": "Usuario eliminado correctamente"}
