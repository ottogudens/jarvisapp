"""
J.A.R.V.I.S. SaaS — Autenticación y Control de Acceso por Roles (RBAC)

Roles del sistema:
  - superadmin : Dueño del sistema. Acceso total.
  - admin      : Co-administrador. Mismo acceso que superadmin.
  - cliente    : Usuario de un tenant. Solo chat y funciones de su perfil de IA.
"""
from typing import Optional
import os
import datetime

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import bcrypt
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import (
    Usuario, Tenant, TenantProfile, JarvisProfile, SaaSPlan, ROL_SUPERADMIN, ROL_ADMIN,
    ROL_CLIENTE, ROLS_STAFF,
)

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

RUNTIME_ENVIRONMENT = os.getenv("APP_ENV", os.getenv("ENVIRONMENT", "development")).lower()
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")
if not SECRET_KEY and RUNTIME_ENVIRONMENT in {"production", "prod"}:
    raise RuntimeError("JWT_SECRET_KEY es obligatoria en producción.")
if not SECRET_KEY:
    import warnings
    warnings.warn(
        "⚠️  JWT_SECRET_KEY no configurada. Usando clave temporal INSEGURA. "
        "NO usar en producción.",
        stacklevel=2,
    )
    SECRET_KEY = "DESARROLLO_LOCAL_INSEGURO_CAMBIAR"

ALGORITHM = "HS256"
TOKEN_EXPIRY_HOURS = 24

# ---------------------------------------------------------------------------
# Hashing de contraseñas
# ---------------------------------------------------------------------------

def verificar_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------

def crear_token_jwt(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.datetime.utcnow() + datetime.timedelta(hours=TOKEN_EXPIRY_HOURS)
    payload["iat"] = datetime.datetime.utcnow()
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


# ---------------------------------------------------------------------------
# Schemas Pydantic
# ---------------------------------------------------------------------------

class ProfileUpdate(BaseModel):
    nombre_organizacion: Optional[str] = None
    nombre_contacto: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    active_profile_ids: Optional[list[int]] = None


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    nombre_organizacion: str
    nombre_contacto: str
    email: str
    password: str
    telefono: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    perfil_jarvis: str
    nombre_organizacion: str
    rol: str
    trial_ends_at: Optional[str] = None
    trial_daily_token_limit: Optional[int] = None


# ---------------------------------------------------------------------------
# Router de autenticación
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/v1/auth", tags=["Autenticacion"])


def _trial_plan(db: Session) -> SaaSPlan:
    """Obtiene el plan interno usado solo durante el período de prueba."""
    plan = db.query(SaaSPlan).filter(SaaSPlan.nombre_plan == "Prueba gratuita").first()
    if plan:
        return plan
    plan = SaaSPlan(
        nombre_plan="Prueba gratuita", tokens_mensuales=35_000,
        precio_mensual=0, moneda="CLP",
    )
    db.add(plan)
    db.flush()
    return plan


def _token_response(usuario: Usuario, db: Session) -> TokenResponse:
    claims = _claims_usuario(usuario, db)
    tenant = usuario.tenant
    return TokenResponse(
        access_token=crear_token_jwt(claims),
        perfil_jarvis=claims["perfil_jarvis"],
        nombre_organizacion=tenant.nombre_organizacion if tenant else "N/A",
        rol=claims["rol"],
        trial_ends_at=tenant.trial_ends_at.isoformat() if tenant and tenant.trial_ends_at else None,
        trial_daily_token_limit=tenant.trial_daily_token_limit if tenant and tenant.is_trial else None,
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: Session = Depends(get_db)):
    """Crea una organización aislada y su primer usuario con 7 días de prueba."""
    email = body.email.strip().lower()
    organization = body.nombre_organizacion.strip()
    contact = body.nombre_contacto.strip()
    password = body.password
    if len(organization) < 2 or len(contact) < 2:
        raise HTTPException(status_code=422, detail="Indica el nombre de tu organización y de contacto.")
    if "@" not in email or len(email) > 100:
        raise HTTPException(status_code=422, detail="Ingresa un correo electrónico válido.")
    if len(password) < 10 or not any(char.isalpha() for char in password) or not any(char.isdigit() for char in password):
        raise HTTPException(status_code=422, detail="La contraseña debe tener al menos 10 caracteres, letras y números.")
    if db.query(Usuario.id_usuario).filter(Usuario.email == email).first():
        raise HTTPException(status_code=409, detail="Ya existe una cuenta con este correo. Inicia sesión.")

    from backend.trial_policy import TRIAL_DAILY_TOKEN_LIMIT, TRIAL_DAYS
    from datetime import timedelta, timezone
    now = datetime.datetime.now(timezone.utc)
    try:
        plan = _trial_plan(db)
        tenant = Tenant(
            nombre_organizacion=organization,
            nombre_contacto=contact,
            telefono=body.telefono.strip() if body.telefono else None,
            id_plan=plan.id_plan,
            is_trial=True,
            trial_ends_at=now + timedelta(days=TRIAL_DAYS),
            trial_daily_token_limit=TRIAL_DAILY_TOKEN_LIMIT,
        )
        db.add(tenant)
        db.flush()
        profile = db.query(JarvisProfile).filter(
            JarvisProfile.nombre == "Asistente Personal para Profesionales"
        ).first()
        if profile:
            db.add(TenantProfile(id_tenant=tenant.id_tenant, id_perfil=profile.id_perfil))
            active_profile_ids = [profile.id_perfil]
        else:
            active_profile_ids = []
        usuario = Usuario(
            id_tenant=tenant.id_tenant,
            email=email,
            password_hash=hash_password(password),
            rol=ROL_CLIENTE,
            active_profile_ids=active_profile_ids,
        )
        db.add(usuario)
        db.commit()
        db.refresh(usuario)
        return _token_response(usuario, db)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="No fue posible crear la cuenta. Verifica el correo e inténtalo nuevamente.")


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: Session = Depends(get_db)):
    """
    Autentica un usuario con email + contraseña y retorna un JWT.
    El token contiene: id_usuario, id_tenant, email, perfil_jarvis, rol, is_superadmin.
    """
    usuario = db.query(Usuario).filter(Usuario.email == body.email).first()

    if not usuario or not verificar_password(body.password, usuario.password_hash):
        raise HTTPException(status_code=401, detail="Credenciales inválidas.")

    # Sincronizar is_superadmin con el campo rol (compatibilidad)
    return _token_response(usuario, db)


# ---------------------------------------------------------------------------
# Dependencies de seguridad
# ---------------------------------------------------------------------------

security = HTTPBearer()


def _claims_usuario(usuario: Usuario, db: Session) -> dict:
    """Construye claims desde el estado actual de la base de datos, no del JWT."""
    rol = usuario.rol or (ROL_SUPERADMIN if usuario.is_superadmin else ROL_CLIENTE)
    permitted_ids = {
        profile_id for (profile_id,) in db.query(TenantProfile.id_perfil).filter(
            TenantProfile.id_tenant == usuario.id_tenant
        ).all()
    }
    active_ids = [
        profile_id for profile_id in (usuario.active_profile_ids or [])
        if isinstance(profile_id, int) and profile_id in permitted_ids
    ]
    perfil = usuario.perfil_jarvis or ""
    if active_ids:
        profile = db.query(JarvisProfile).filter(
            JarvisProfile.id_perfil == active_ids[0]
        ).first()
        if profile:
            perfil = profile.nombre
    return {
        "id_usuario": usuario.id_usuario,
        "id_tenant": usuario.id_tenant,
        "session_version": usuario.session_version or 0,
        "email": usuario.email,
        "perfil_jarvis": perfil,
        "active_profile_ids": active_ids,
        "active_custom_profile_id": usuario.active_custom_profile_id,
        "rol": rol,
        "is_superadmin": rol == ROL_SUPERADMIN,
    }


async def obtener_usuario_actual(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> dict:
    """
    Dependency de FastAPI: decodifica el JWT del header Authorization
    y retorna el payload como dict.
    """
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado. Inicie sesión nuevamente.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido.")

    if "id_usuario" not in payload or "id_tenant" not in payload:
        raise HTTPException(status_code=401, detail="Token con payload incompleto.")

    usuario = db.query(Usuario).filter(
        Usuario.id_usuario == payload["id_usuario"],
        Usuario.id_tenant == payload["id_tenant"],
    ).first()
    if not usuario:
        raise HTTPException(status_code=401, detail="La sesión ya no es válida.")
    if payload.get("session_version") != (usuario.session_version or 0):
        raise HTTPException(status_code=401, detail="La sesión fue revocada. Inicie sesión nuevamente.")
    tenant = db.query(Tenant).filter(Tenant.id_tenant == usuario.id_tenant).first()
    rol = usuario.rol or (ROL_SUPERADMIN if usuario.is_superadmin else ROL_CLIENTE)
    if tenant and not tenant.is_active and rol not in ROLS_STAFF:
        raise HTTPException(status_code=403, detail="La cuenta de esta organización está suspendida. Contacta al administrador de Bonso.")
    return _claims_usuario(usuario, db)


def invalidar_sesiones(usuario: Usuario) -> None:
    """Invalida todos los JWT ya emitidos para un usuario."""
    usuario.session_version = (usuario.session_version or 0) + 1


async def requiere_staff(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> dict:
    """
    Requiere rol 'superadmin' o 'admin'.
    Usado para proteger el panel de administración completo.
    """
    payload = await obtener_usuario_actual(credentials, db)
    if payload.get("rol") not in ROLS_STAFF:
        raise HTTPException(
            status_code=403,
            detail="Acceso denegado. Se requiere rol Admin o SuperAdmin.",
        )
    return payload


async def requiere_superadmin(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> dict:
    """
    Requiere específicamente rol 'superadmin'.
    Para operaciones solo del dueño del sistema (ej. gestionar otros admins).
    """
    payload = await obtener_usuario_actual(credentials, db)
    if payload.get("rol") != ROL_SUPERADMIN:
        raise HTTPException(
            status_code=403,
            detail="Acceso denegado. Requiere privilegios de SuperAdmin.",
        )
    return payload


def requiere_feature(feature_requerido: str):
    """
    Factory de dependencia: verifica acceso a un módulo específico según el rol.
    Staff (admin/superadmin) tiene acceso a todo.
    Clientes solo acceden si su perfil_jarvis está en la lista permitida.
    """
    PERMISOS = {
        "modulo_erp": ["Mecanico"],
        "modulo_inspeccion": ["Inspector_DGC"],
        "modulo_enfermeria": ["Enfermera_Paliativos"],
    }

    async def _verificar(
        credentials: HTTPAuthorizationCredentials = Depends(security),
        db: Session = Depends(get_db),
    ) -> dict:
        payload = await obtener_usuario_actual(credentials, db)

        # Staff siempre tiene acceso
        if payload.get("rol") in ROLS_STAFF:
            return payload

        perfil = payload.get("perfil_jarvis", "")
        perfiles_permitidos = PERMISOS.get(feature_requerido, [])
        if perfiles_permitidos and perfil not in perfiles_permitidos:
            raise HTTPException(
                status_code=403,
                detail=f"Acceso denegado. Perfil '{perfil}' no tiene permiso para '{feature_requerido}'.",
            )
        return payload

    return _verificar


def requiere_plan(feature_requerido: str):
    """Autoriza una integración según el plan vigente del tenant."""
    feature_columns = {
        "iot": "permite_iot",
        "mikrotik": "permite_mikrotik",
        "telegram": "permite_telegram",
    }
    if feature_requerido not in feature_columns:
        raise ValueError(f"Feature de plan desconocida: {feature_requerido}")

    async def _verificar(
        credentials: HTTPAuthorizationCredentials = Depends(security),
        db: Session = Depends(get_db),
    ) -> dict:
        payload = await obtener_usuario_actual(credentials, db)
        tenant = db.query(Tenant).filter(Tenant.id_tenant == payload["id_tenant"]).first()
        if not tenant or not tenant.plan or not getattr(tenant.plan, feature_columns[feature_requerido]):
            raise HTTPException(status_code=403, detail="Esta integración no está habilitada para el tenant.")
        return payload

    return _verificar


# ---------------------------------------------------------------------------
# Endpoints de perfil propio
# ---------------------------------------------------------------------------

@router.put('/profile')
def update_profile(
    data: ProfileUpdate,
    usuario: dict = Depends(obtener_usuario_actual),
    db: Session = Depends(get_db)
):
    from backend.models import Tenant
    user = db.query(Usuario).filter(Usuario.id_usuario == usuario['id_usuario']).first()
    if not user:
        raise HTTPException(status_code=404, detail='Usuario no encontrado')

    is_staff = (user.rol or ROL_CLIENTE) in ROLS_STAFF
    tenant_fields_requested = any(
        value is not None for value in (
            data.nombre_organizacion, data.nombre_contacto, data.telefono,
        )
    )
    if tenant_fields_requested and not is_staff:
        raise HTTPException(
            status_code=403,
            detail="Solo un administrador puede modificar la organización o los perfiles activos.",
        )

    tenant = db.query(Tenant).filter(Tenant.id_tenant == user.id_tenant).first()
    if is_staff and tenant:
        if data.nombre_organizacion is not None:
            tenant.nombre_organizacion = data.nombre_organizacion
        if data.nombre_contacto is not None:
            tenant.nombre_contacto = data.nombre_contacto
        if data.telefono is not None:
            tenant.telefono = data.telefono

    if data.email and user.email != data.email:
        existing = db.query(Usuario).filter(Usuario.email == data.email).first()
        if existing:
            raise HTTPException(status_code=400, detail='El email ya está en uso')
        user.email = data.email

    if data.password:
        user.password_hash = bcrypt.hashpw(data.password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        invalidar_sesiones(user)

    # El perfil activo es una preferencia individual. Un cliente puede escoger
    # cualquiera de los perfiles asignados a su organización, pero no otros.
    if data.active_profile_ids is not None:
        permitted_ids = {
            profile_id for (profile_id,) in db.query(TenantProfile.id_perfil).filter(
                TenantProfile.id_tenant == user.id_tenant
            ).all()
        }
        requested_ids = set(data.active_profile_ids)
        if not requested_ids.issubset(permitted_ids):
            raise HTTPException(status_code=400, detail="Se solicitaron perfiles no asignados al tenant.")
        # Conservamos la selección múltiple histórica para staff (enrutamiento
        # automático), mientras que el cliente elige un perfil explícito.
        if not is_staff and len(requested_ids) > 1:
            raise HTTPException(status_code=400, detail="Selecciona un único perfil activo para cada conversación.")
        user.active_profile_ids = data.active_profile_ids

    db.commit()
    return {'message': 'Perfil actualizado correctamente'}


@router.post('/logout')
def logout(
    usuario: dict = Depends(obtener_usuario_actual),
    db: Session = Depends(get_db),
):
    """Revoca los JWT activos del usuario antes de limpiar el dispositivo local."""
    user = db.query(Usuario).filter(Usuario.id_usuario == usuario['id_usuario']).first()
    if user:
        invalidar_sesiones(user)
        db.commit()
    return {'message': 'Sesión cerrada correctamente'}


@router.get('/profile')
def get_profile(
    usuario: dict = Depends(obtener_usuario_actual),
    db: Session = Depends(get_db)
):
    from backend.models import Tenant, TenantProfile, CustomAssistantProfile
    user = db.query(Usuario).filter(Usuario.id_usuario == usuario['id_usuario']).first()
    if not user:
        raise HTTPException(status_code=404, detail='Usuario no encontrado')

    tenant = db.query(Tenant).filter(Tenant.id_tenant == user.id_tenant).first()
    from backend.models import SaaSPlan
    plan = db.query(SaaSPlan).filter(SaaSPlan.id_plan == tenant.id_plan).first() if tenant else None

    tp_list = db.query(TenantProfile).filter(TenantProfile.id_tenant == user.id_tenant).all()
    perfiles = [{"id_perfil": tp.perfil.id_perfil, "nombre": tp.perfil.nombre, "instrucciones_extra": tp.instrucciones_extra} for tp in tp_list]
    custom_profile = None
    if user.active_custom_profile_id:
        custom_profile = db.query(CustomAssistantProfile).filter(
            CustomAssistantProfile.id_profile == user.active_custom_profile_id,
            CustomAssistantProfile.id_tenant == user.id_tenant,
            CustomAssistantProfile.estado == "active",
        ).first()

    return {
        'email': user.email,
        'nombre_organizacion': tenant.nombre_organizacion if tenant else '',
        'nombre_contacto': tenant.nombre_contacto if tenant else '',
        'telefono': tenant.telefono if tenant else '',
        'rol': user.rol or (ROL_SUPERADMIN if user.is_superadmin else ROL_CLIENTE),
        'is_superadmin': (user.rol == ROL_SUPERADMIN) if user.rol else user.is_superadmin,
        'active_profile_ids': user.active_profile_ids,
        'active_custom_profile': {"id_profile": custom_profile.id_profile, "nombre": custom_profile.nombre} if custom_profile else None,
        'perfiles': perfiles,
        'plan_features': {
            'telegram': plan.permite_telegram if plan else False,
            'whatsapp': plan.permite_whatsapp if plan else False,
            'iot': plan.permite_iot if plan else False,
            'mikrotik': plan.permite_mikrotik if plan else False,
        }
    }
