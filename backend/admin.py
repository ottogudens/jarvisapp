from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
import os
import bcrypt

from backend.database import get_db
from backend.models import Usuario, Tenant, SaaSPlan, SystemSettings, AIUsageStats, BillingSubscription, KnowledgeDocument, KnowledgeIngestionJob, KnowledgeRetrievalAudit, TelegramWebhookEvent, ROL_SUPERADMIN, ROL_ADMIN, ROL_CLIENTE, ROLS_STAFF
from backend.auth import obtener_usuario_actual, hash_password, invalidar_sesiones, requiere_staff, requiere_superadmin
from backend.crypto_utils import encrypt_secret

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
    permite_iot: bool
    permite_mikrotik: bool
    permite_telegram: bool = False
    permite_whatsapp: bool = False
    tokens_mensuales: int = 100000
    max_documentos: int = Field(default=100, ge=1, le=1_000_000)
    almacenamiento_bytes: int = Field(default=1073741824, ge=1_048_576)
    max_upload_bytes: int = Field(default=15728640, ge=1_024, le=15_728_640)
    precio_mensual: int = 0
    moneda: str = "CLP"

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
    active_profile_ids: List[int] = []
    is_active: bool = True
    suspension_reason: Optional[str] = None
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
    primary_profile_id: Optional[int] = None

class TenantUpdateSchema(BaseModel):
    nombre_organizacion: Optional[str] = None
    nombre_contacto: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    id_plan: Optional[int] = None
    ai_provider: Optional[str] = None
    ai_model: Optional[str] = None
    perfiles_ids: Optional[List[int]] = None
    primary_profile_id: Optional[int] = None
    is_active: Optional[bool] = None
    suspension_reason: Optional[str] = None

class UsuarioSchema(BaseModel):
    id_usuario: int
    email: str
    rol: str
    active_profile_ids: list[int] = []

class UsuarioCreateSchema(BaseModel):
    email: str
    password: str
    rol: str = ROL_CLIENTE
    active_profile_ids: list[int] = []

class UsuarioUpdateSchema(BaseModel):
    email: Optional[str] = None
    password: Optional[str] = None
    rol: Optional[str] = None
    active_profile_ids: list[int] = []


class TenantStatusSchema(BaseModel):
    is_active: bool
    reason: Optional[str] = None


class OperationsConfigSchema(BaseModel):
    invoice_automation_enabled: bool = False
    invoice_day: int = 1
    invoice_sender_name: str = "Bonso"
    invoice_reply_to: Optional[str] = None


def _knowledge_overview(db: Session) -> dict:
    """Métricas sin contenido de documentos, aptas para operación SaaS."""
    now = datetime.now(timezone.utc)
    stale_before = now - timedelta(minutes=15)
    documents = db.query(KnowledgeDocument).all()
    jobs = db.query(KnowledgeIngestionJob).all()
    tenants = {tenant.id_tenant: tenant.nombre_organizacion for tenant in db.query(Tenant).all()}
    status_counts = {status: 0 for status in ("queued", "processing", "ready", "failed", "superseded")}
    per_tenant = {}
    for document in documents:
        status_counts[document.status] = status_counts.get(document.status, 0) + 1
        row = per_tenant.setdefault(document.id_tenant, {"documents": 0, "ready": 0, "failed": 0, "queued": 0, "bytes": 0})
        row["documents"] += 1
        row["bytes"] += document.byte_size or 0
        if document.status in row:
            row[document.status] += 1
    stale_jobs = [job for job in jobs if job.status == "processing" and job.started_at and job.started_at < stale_before]
    failed_jobs = [job for job in jobs if job.status == "failed"]
    heartbeat_setting = db.query(SystemSettings).filter(SystemSettings.key == "KNOWLEDGE_WORKER_HEARTBEAT").first()
    heartbeat_at = None
    try:
        heartbeat_at = datetime.fromisoformat(heartbeat_setting.value) if heartbeat_setting else None
        if heartbeat_at and heartbeat_at.tzinfo is None:
            heartbeat_at = heartbeat_at.replace(tzinfo=timezone.utc)
    except ValueError:
        heartbeat_at = None
    worker_healthy = bool(heartbeat_at and now - heartbeat_at < timedelta(minutes=5))
    alerts = []
    if stale_jobs:
        alerts.append({"severity": "critical", "type": "stalled_jobs", "message": f"{len(stale_jobs)} trabajo(s) lleva(n) más de 15 minutos procesando."})
    if failed_jobs:
        alerts.append({"severity": "warning", "type": "failed_jobs", "message": f"{len(failed_jobs)} documento(s) requieren revisión o reintento."})
    if status_counts.get("queued", 0) >= 20:
        alerts.append({"severity": "warning", "type": "queue_backlog", "message": f"La cola documental acumula {status_counts['queued']} trabajo(s)."})
    if not worker_healthy:
        alerts.append({"severity": "critical", "type": "worker_offline", "message": "No se ha recibido heartbeat del worker documental en los últimos 5 minutos."})
    tenant_rows = [
        {"id_tenant": tenant_id, "organization": tenants.get(tenant_id, "Organización"), **values}
        for tenant_id, values in per_tenant.items()
    ]
    tenant_rows.sort(key=lambda item: (item["failed"] == 0, -item["queued"], -item["bytes"]))
    return {
        "totals": {**status_counts, "documents": len(documents), "storage_bytes": sum(doc.byte_size or 0 for doc in documents), "retrievals": db.query(KnowledgeRetrievalAudit).count()},
        "workers": {"queued_jobs": sum(job.status == "queued" for job in jobs), "processing_jobs": sum(job.status == "processing" for job in jobs), "failed_jobs": len(failed_jobs), "stalled_jobs": len(stale_jobs), "healthy": worker_healthy, "heartbeat_at": heartbeat_at.isoformat() if heartbeat_at else None},
        "alerts": alerts,
        "tenants": tenant_rows[:100],
        "recent_failures": [{"document_id": job.id_document, "error_message": job.error_message, "attempts": job.attempts, "finished_at": job.finished_at.isoformat() if job.finished_at else None} for job in sorted(failed_jobs, key=lambda job: job.finished_at or now, reverse=True)[:20]],
    }


def _security_overview(db: Session) -> dict:
    """Indicadores agregados, sin exponer chats, tokens ni datos de usuarios."""
    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=24)
    events = db.query(TelegramWebhookEvent).filter(TelegramWebhookEvent.created_at >= since).all()
    def retention_days(name: str, default: int) -> int:
        try:
            return max(1, int(os.getenv(name, str(default))))
        except ValueError:
            return default
    return {
        "telegram_updates_24h": len(events),
        "telegram_completed_24h": sum(event.status == "completed" for event in events),
        "telegram_processing_24h": sum(event.status == "processing" for event in events),
        "revocation_enabled": True,
        "rag_audit_retention_days": retention_days("RAG_AUDIT_RETENTION_DAYS", 90),
        "telegram_event_retention_days": retention_days("TELEGRAM_WEBHOOK_RETENTION_DAYS", 30),
    }

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


@router.get("/operations/overview")
def operations_overview(usuario: dict = Depends(requiere_staff), db: Session = Depends(get_db)):
    subscriptions = db.query(BillingSubscription).order_by(BillingSubscription.updated_at.desc()).all()
    tenants = db.query(Tenant).all()
    tenant_by_id = {tenant.id_tenant: tenant for tenant in tenants}
    latest_by_tenant = {}
    for subscription in subscriptions:
        latest_by_tenant.setdefault(subscription.id_tenant, subscription)
    current_subscriptions = list(latest_by_tenant.values())
    active_subscriptions = [sub for sub in current_subscriptions if sub.status in {"authorized", "active"}]
    providers = {}
    for stat in db.query(AIUsageStats).all():
        item = providers.setdefault(stat.proveedor, {"provider": stat.proveedor, "tokens": 0, "requests": 0})
        item["tokens"] += stat.tokens_consumidos or 0
        item["requests"] += stat.solicitudes_realizadas or 0
    def setting_value(key: str, default: str = "") -> str:
        value = db.query(SystemSettings).filter(SystemSettings.key == key).first()
        return value.value if value else default
    invoice_config = {
        "enabled": setting_value("INVOICE_AUTOMATION_ENABLED", "false").lower() == "true",
        "day": int(setting_value("INVOICE_AUTOMATION_DAY", "1") or 1),
        "sender_name": setting_value("INVOICE_SENDER_NAME", "Bonso"),
        "reply_to": setting_value("INVOICE_REPLY_TO", "") or None,
    }
    customer_rows = []
    for tenant in tenants:
        primary_user = db.query(Usuario).filter(Usuario.id_tenant == tenant.id_tenant).order_by(Usuario.id_usuario).first()
        usage = db.query(func.coalesce(func.sum(Usuario.tokens_consumidos), 0)).filter(Usuario.id_tenant == tenant.id_tenant).scalar() or 0
        last_usage = db.query(func.max(AIUsageStats.fecha_registro)).filter(AIUsageStats.id_tenant == tenant.id_tenant).scalar()
        subscription = latest_by_tenant.get(tenant.id_tenant)
        customer_rows.append({
            "id_tenant": tenant.id_tenant, "organization": tenant.nombre_organizacion,
            "contact": tenant.nombre_contacto, "phone": tenant.telefono,
            "email": primary_user.email if primary_user else None,
            "ai_provider": tenant.ai_provider, "ai_model": tenant.ai_model,
            "plan": tenant.plan.nombre_plan if tenant.plan else "Sin plan",
            "active": tenant.is_active, "trial": tenant.is_trial,
            "trial_ends_at": tenant.trial_ends_at.isoformat() if tenant.trial_ends_at else None,
            "tokens": int(usage), "last_activity": last_usage.isoformat() if last_usage else None,
            "subscription_status": subscription.status if subscription else "none",
        })
    customer_rows.sort(key=lambda row: (not row["active"], row["organization"].lower()))
    return {
        "kpis": {
            "clientes": len(tenants), "clientes_activos": sum(1 for tenant in tenants if tenant.is_active),
            "clientes_suspendidos": sum(1 for tenant in tenants if not tenant.is_active),
            "pruebas_activas": sum(1 for tenant in tenants if tenant.is_trial and tenant.trial_ends_at and tenant.trial_ends_at > datetime.now(timezone.utc)),
            "suscripciones_activas": len(active_subscriptions), "cobros_pendientes": sum(1 for sub in current_subscriptions if sub.status == "pending"),
            "mrr": sum(sub.amount or 0 for sub in active_subscriptions), "tokens": db.query(func.sum(Usuario.tokens_consumidos)).scalar() or 0,
        },
        "subscriptions": [{"id_tenant": sub.id_tenant, "organizacion": tenant_by_id.get(sub.id_tenant).nombre_organizacion if tenant_by_id.get(sub.id_tenant) else "Organización", "plan_id": sub.id_plan, "status": sub.status, "amount": sub.amount, "currency": sub.currency, "updated_at": sub.updated_at.isoformat() if sub.updated_at else None} for sub in subscriptions[:100]],
        "customers": customer_rows,
        "ai_providers": sorted(providers.values(), key=lambda item: item["tokens"], reverse=True),
        "integration_status": {
            "mercado_pago_access_token": bool(os.getenv("MP_ACCESS_TOKEN")),
            "mercado_pago_webhook": bool(os.getenv("MP_WEBHOOK_SECRET")),
            "openai": bool(setting_value("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")),
            "anthropic": bool(setting_value("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_API_KEY")),
            "deepseek": bool(setting_value("DEEPSEEK_API_KEY") or os.getenv("DEEPSEEK_API_KEY")),
            "gemini": bool(setting_value("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")),
        },
        "invoice_automation": invoice_config,
        "knowledge": _knowledge_overview(db),
        "security": _security_overview(db),
    }


@router.get("/knowledge/overview")
def knowledge_overview(usuario: dict = Depends(requiere_staff), db: Session = Depends(get_db)):
    return _knowledge_overview(db)


@router.post("/operations/tenants/{id_tenant}/status")
def set_tenant_status(id_tenant: int, data: TenantStatusSchema, usuario: dict = Depends(requiere_staff), db: Session = Depends(get_db)):
    tenant = db.query(Tenant).filter(Tenant.id_tenant == id_tenant).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Cliente no encontrado.")
    if tenant.id_tenant == usuario["id_tenant"] and not data.is_active:
        raise HTTPException(status_code=400, detail="No puedes suspender tu propia organización administrativa.")
    tenant.is_active = data.is_active
    tenant.suspended_at = None if data.is_active else datetime.now(timezone.utc)
    tenant.suspension_reason = None if data.is_active else (data.reason or "Suspendido por administración")[:255]
    db.commit()
    return {"id_tenant": tenant.id_tenant, "is_active": tenant.is_active, "reason": tenant.suspension_reason}


@router.get("/operations/config", response_model=OperationsConfigSchema)
def get_operations_config(usuario: dict = Depends(requiere_staff), db: Session = Depends(get_db)):
    def value(key: str, default: str) -> str:
        setting = db.query(SystemSettings).filter(SystemSettings.key == key).first()
        return setting.value if setting else default
    return OperationsConfigSchema(
        invoice_automation_enabled=value("INVOICE_AUTOMATION_ENABLED", "false").lower() == "true",
        invoice_day=max(1, min(28, int(value("INVOICE_AUTOMATION_DAY", "1") or 1))),
        invoice_sender_name=value("INVOICE_SENDER_NAME", "Bonso"),
        invoice_reply_to=value("INVOICE_REPLY_TO", "") or None,
    )


@router.put("/operations/config", response_model=OperationsConfigSchema)
def save_operations_config(data: OperationsConfigSchema, usuario: dict = Depends(requiere_staff), db: Session = Depends(get_db)):
    if not 1 <= data.invoice_day <= 28:
        raise HTTPException(status_code=422, detail="El día de facturación debe estar entre 1 y 28.")
    values = {
        "INVOICE_AUTOMATION_ENABLED": str(data.invoice_automation_enabled).lower(),
        "INVOICE_AUTOMATION_DAY": str(data.invoice_day),
        "INVOICE_SENDER_NAME": data.invoice_sender_name.strip() or "Bonso",
        "INVOICE_REPLY_TO": (data.invoice_reply_to or "").strip(),
    }
    for key, value in values.items():
        setting = db.query(SystemSettings).filter(SystemSettings.key == key).first()
        if setting: setting.value = value
        else: db.add(SystemSettings(key=key, value=value))
    db.commit()
    return get_operations_config(usuario, db)

# --- Endpoints Configuraciones IA ---
class AIKeysSchema(BaseModel):
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    deepseek_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None

@router.get("/ai-keys", response_model=AIKeysSchema)
def get_ai_keys(usuario: dict = Depends(requiere_staff), db: Session = Depends(get_db)):
    # Las claves nunca se devuelven después de almacenarse. Una actualización
    # posterior debe enviar el valor completo de reemplazo.
    return AIKeysSchema()

@router.post("/ai-keys")
def save_ai_keys(keys: AIKeysSchema, usuario: dict = Depends(requiere_staff), db: Session = Depends(get_db)):
    def update_or_create(key_name: str, value: str):
        if not value: return
        setting = db.query(SystemSettings).filter(SystemSettings.key == key_name).first()
        if setting:
            setting.value = encrypt_secret(value)
        else:
            db.add(SystemSettings(key=key_name, value=encrypt_secret(value)))
            
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
        permite_iot=plan.permite_iot,
        permite_mikrotik=plan.permite_mikrotik,
        permite_telegram=plan.permite_telegram,
        permite_whatsapp=plan.permite_whatsapp, tokens_mensuales=plan.tokens_mensuales,
        max_documentos=plan.max_documentos, almacenamiento_bytes=plan.almacenamiento_bytes, max_upload_bytes=plan.max_upload_bytes,
        precio_mensual=plan.precio_mensual, moneda=plan.moneda,
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
    db_plan.permite_iot = plan.permite_iot
    db_plan.permite_mikrotik = plan.permite_mikrotik
    db_plan.permite_telegram = plan.permite_telegram
    db_plan.permite_whatsapp = plan.permite_whatsapp
    db_plan.tokens_mensuales = plan.tokens_mensuales
    db_plan.max_documentos = plan.max_documentos
    db_plan.almacenamiento_bytes = plan.almacenamiento_bytes
    db_plan.max_upload_bytes = plan.max_upload_bytes
    db_plan.precio_mensual = plan.precio_mensual
    db_plan.moneda = plan.moneda
    
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

class TenantProfileUpdatePayload(BaseModel):
    id_perfil: int
    instrucciones_extra: str

@router.put("/tenant/profiles")
def update_tenant_profile_instructions(
    data: TenantProfileUpdatePayload,
    usuario: dict = Depends(obtener_usuario_actual),
    db: Session = Depends(get_db)
):
    """Actualiza las instrucciones extra de un perfil J.A.R.V.I.S. para un Tenant."""
    from backend.models import TenantProfile
    id_tenant = usuario["id_tenant"]
    
    tp = db.query(TenantProfile).filter(
        TenantProfile.id_tenant == id_tenant,
        TenantProfile.id_perfil == data.id_perfil
    ).first()
    
    if not tp:
        tp = TenantProfile(
            id_tenant=id_tenant,
            id_perfil=data.id_perfil,
            instrucciones_extra=data.instrucciones_extra
        )
        db.add(tp)
    else:
        tp.instrucciones_extra = data.instrucciones_extra
        
    db.commit()
    return {"status": "success", "message": "Instrucciones del cliente guardadas exitosamente"}

# --- Endpoints Tenants (CRUD Completo) ---

def _normalizar_email(email: str) -> str:
    normalized = (email or "").strip().lower()
    if not normalized or "@" not in normalized:
        raise HTTPException(status_code=422, detail="Ingresa un correo electrónico válido.")
    return normalized


def _validar_contrasena(password: Optional[str]) -> Optional[str]:
    """Normaliza una contraseña administrativa opcional y aplica la política de acceso."""
    if password is None or not password.strip():
        return None
    normalized = password.strip()
    if len(normalized) < 10 or not any(char.isalpha() for char in normalized) or not any(char.isdigit() for char in normalized):
        raise HTTPException(
            status_code=422,
            detail="La contraseña debe tener al menos 10 caracteres, letras y números.",
        )
    return normalized


def _validar_perfiles(db: Session, profile_ids: List[int]) -> List[int]:
    """Evita asignaciones huérfanas o duplicadas de perfiles a un cliente."""
    normalized_ids = list(dict.fromkeys(profile_ids))
    if not normalized_ids:
        return []
    from backend.models import JarvisProfile
    found_ids = {
        profile_id for (profile_id,) in db.query(JarvisProfile.id_perfil)
        .filter(JarvisProfile.id_perfil.in_(normalized_ids))
        .all()
    }
    missing = sorted(set(normalized_ids) - found_ids)
    if missing:
        raise HTTPException(status_code=422, detail=f"Perfiles inexistentes: {', '.join(map(str, missing))}.")
    return normalized_ids


def _sincronizar_perfiles_activos(users: List[Usuario], allowed_ids: List[int], primary_profile_id: Optional[int] = None) -> None:
    """Mantiene las preferencias de cada usuario dentro de los perfiles asignados al tenant."""
    allowed = set(allowed_ids)
    for user in users:
        current = [profile_id for profile_id in (user.active_profile_ids or []) if profile_id in allowed]
        if primary_profile_id is not None and user.rol == ROL_CLIENTE:
            current = [primary_profile_id]
        elif not current and allowed_ids:
            current = [allowed_ids[0]]
        user.active_profile_ids = current

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
            active_profile_ids=user.active_profile_ids if user else [],
            is_active=t.is_active,
            suspension_reason=t.suspension_reason,
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

    email = _normalizar_email(data.email)
    password = _validar_contrasena(data.password)
    if password is None:
        raise HTTPException(status_code=422, detail="Define una contraseña inicial segura para el cliente.")
    profile_ids = _validar_perfiles(db, data.perfiles_ids)
    if data.primary_profile_id is not None and data.primary_profile_id not in profile_ids:
        raise HTTPException(status_code=422, detail="El perfil inicial debe estar asignado al cliente.")

    # Validar que el email no exista
    existing = db.query(Usuario).filter(Usuario.email == email).first()
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
    for p_id in profile_ids:
        db.add(TenantProfile(id_tenant=new_tenant.id_tenant, id_perfil=p_id))

    # Crear usuario principal del tenant
    new_user = Usuario(
        id_tenant=new_tenant.id_tenant,
        email=email,
        password_hash=hash_password(password),
        rol=ROL_CLIENTE,
        is_superadmin=False
    )
    if data.primary_profile_id is not None:
        new_user.active_profile_ids = [data.primary_profile_id]
    elif profile_ids:
        new_user.active_profile_ids = [profile_ids[0]]
    else:
        new_user.active_profile_ids = []
        
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

    password = _validar_contrasena(update_data.password)
    
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
        
    assigned_profile_ids = None
    if update_data.perfiles_ids is not None:
        assigned_profile_ids = _validar_perfiles(db, update_data.perfiles_ids)
        if update_data.primary_profile_id is not None and update_data.primary_profile_id not in assigned_profile_ids:
            raise HTTPException(status_code=422, detail="El perfil inicial debe estar asignado al cliente.")
        # Reemplazar perfiles actuales
        db.query(TenantProfile).filter(TenantProfile.id_tenant == id_tenant).delete()
        for p_id in assigned_profile_ids:
            db.add(TenantProfile(id_tenant=id_tenant, id_perfil=p_id))

    if update_data.is_active is not None:
        if db_tenant.id_tenant == usuario["id_tenant"] and not update_data.is_active:
            raise HTTPException(status_code=400, detail="No puedes suspender tu propia organización administrativa.")
        db_tenant.is_active = update_data.is_active
        db_tenant.suspended_at = None if update_data.is_active else datetime.now(timezone.utc)
        db_tenant.suspension_reason = None if update_data.is_active else (update_data.suspension_reason or "Suspendido por administración")[:255]

    # Actualizar email y/o contraseña del usuario administrador del tenant
    if update_data.email is not None or password is not None:
        admin_user = db.query(Usuario).filter(Usuario.id_tenant == id_tenant).first()
        if admin_user:
            if update_data.email is not None:
                email = _normalizar_email(update_data.email)
                existing = db.query(Usuario).filter(Usuario.email == email, Usuario.id_usuario != admin_user.id_usuario).first()
                if existing:
                    raise HTTPException(status_code=400, detail="El email ya está en uso por otro usuario")
                admin_user.email = email
            if password is not None:
                admin_user.password_hash = hash_password(password)
                invalidar_sesiones(admin_user)

    users = db.query(Usuario).filter(Usuario.id_tenant == id_tenant).all()
    if assigned_profile_ids is not None:
        _sincronizar_perfiles_activos(users, assigned_profile_ids, update_data.primary_profile_id)
    elif update_data.primary_profile_id is not None:
        current_profile_ids = [profile.id_perfil for profile in db.query(TenantProfile).filter(TenantProfile.id_tenant == id_tenant).all()]
        if update_data.primary_profile_id not in current_profile_ids:
            raise HTTPException(status_code=422, detail="El perfil inicial debe estar asignado al cliente.")
        _sincronizar_perfiles_activos(users, current_profile_ids, update_data.primary_profile_id)
    
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
    from litellm import completion
    import os
    
    provider = data.provider.lower()
    
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

    env_key = "ANTHROPIC_API_KEY" if provider in {"anthropic", "claude"} else f"{provider.upper()}_API_KEY"
    previous_value = os.environ.get(env_key)

    try:
        # LiteLLM obtiene la credencial desde el entorno; se restaura siempre
        # para no dejar una clave ingresada por HTTP en el proceso global.
        os.environ[env_key] = data.api_key
        response = completion(
            model=model,
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=5
        )
        return {"status": "ok", "message": "Key is valid"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if previous_value is None:
            os.environ.pop(env_key, None)
        else:
            os.environ[env_key] = previous_value

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
        active_profile_ids=u.active_profile_ids or []
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
        active_profile_ids=data.active_profile_ids or []
    )
    db.add(nuevo_usuario)
    db.commit()
    db.refresh(nuevo_usuario)

    return UsuarioSchema(
        id_usuario=nuevo_usuario.id_usuario,
        email=nuevo_usuario.email,
        rol=nuevo_usuario.rol,
        active_profile_ids=nuevo_usuario.active_profile_ids or []
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
        invalidar_sesiones(target_user)

    if data.rol:
        if data.rol == ROL_SUPERADMIN and usuario.get("rol") != ROL_SUPERADMIN:
            raise HTTPException(status_code=403, detail="Solo un superadmin puede asignar el rol de superadmin")
        target_user.rol = data.rol
        target_user.is_superadmin = (data.rol == ROL_SUPERADMIN)
        invalidar_sesiones(target_user)

    if data.active_profile_ids is not None:
        target_user.active_profile_ids = data.active_profile_ids

    db.commit()
    db.refresh(target_user)

    return UsuarioSchema(
        id_usuario=target_user.id_usuario,
        email=target_user.email,
        rol=target_user.rol,
        active_profile_ids=target_user.active_profile_ids or []
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
