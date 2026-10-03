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
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import (
    Usuario, Tenant, TenantProfile, JarvisProfile, ROL_SUPERADMIN, ROL_ADMIN,
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


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    perfil_jarvis: str
    nombre_organizacion: str
    rol: str


# ---------------------------------------------------------------------------
# Router de autenticación
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/v1/auth", tags=["Autenticacion"])


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
    rol_usuario = usuario.rol or (ROL_SUPERADMIN if usuario.is_superadmin else ROL_CLIENTE)

    claims = _claims_usuario(usuario, db)
    token = crear_token_jwt(claims)

    tenant = usuario.tenant
    return TokenResponse(
        access_token=token,
        perfil_jarvis=claims["perfil_jarvis"],
        nombre_organizacion=tenant.nombre_organizacion if tenant else "N/A",
        rol=rol_usuario,
    )


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
        "email": usuario.email,
        "perfil_jarvis": perfil,
        "active_profile_ids": active_ids,
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
    return _claims_usuario(usuario, db)


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
            data.active_profile_ids,
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

    if is_staff and data.active_profile_ids is not None:
        permitted_ids = {
            profile_id for (profile_id,) in db.query(TenantProfile.id_perfil).filter(
                TenantProfile.id_tenant == user.id_tenant
            ).all()
        }
        requested_ids = set(data.active_profile_ids)
        if not requested_ids.issubset(permitted_ids):
            raise HTTPException(status_code=400, detail="Se solicitaron perfiles no asignados al tenant.")
        user.active_profile_ids = data.active_profile_ids

    db.commit()
    return {'message': 'Perfil actualizado correctamente'}


@router.get('/profile')
def get_profile(
    usuario: dict = Depends(obtener_usuario_actual),
    db: Session = Depends(get_db)
):
    from backend.models import Tenant, TenantProfile
    user = db.query(Usuario).filter(Usuario.id_usuario == usuario['id_usuario']).first()
    if not user:
        raise HTTPException(status_code=404, detail='Usuario no encontrado')

    tenant = db.query(Tenant).filter(Tenant.id_tenant == user.id_tenant).first()
    from backend.models import SaaSPlan
    plan = db.query(SaaSPlan).filter(SaaSPlan.id_plan == tenant.id_plan).first() if tenant else None

    tp_list = db.query(TenantProfile).filter(TenantProfile.id_tenant == user.id_tenant).all()
    perfiles = [{"id_perfil": tp.perfil.id_perfil, "nombre": tp.perfil.nombre, "instrucciones_extra": tp.instrucciones_extra} for tp in tp_list]

    return {
        'email': user.email,
        'nombre_organizacion': tenant.nombre_organizacion if tenant else '',
        'nombre_contacto': tenant.nombre_contacto if tenant else '',
        'telefono': tenant.telefono if tenant else '',
        'rol': user.rol or (ROL_SUPERADMIN if user.is_superadmin else ROL_CLIENTE),
        'is_superadmin': (user.rol == ROL_SUPERADMIN) if user.rol else user.is_superadmin,
        'active_profile_ids': user.active_profile_ids,
        'perfiles': perfiles,
        'plan_features': {
            'telegram': plan.permite_telegram if plan else False,
            'whatsapp': plan.permite_whatsapp if plan else False,
            'iot': plan.permite_iot if plan else False,
            'mikrotik': plan.permite_mikrotik if plan else False,
        }
    }
