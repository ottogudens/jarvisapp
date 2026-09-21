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
from backend.models import Usuario, ROL_SUPERADMIN, ROL_ADMIN, ROL_CLIENTE, ROLS_STAFF

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")
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
    nombre_organizacion: str
    nombre_contacto: Optional[str] = None
    telefono: Optional[str] = None
    email: str
    password: Optional[str] = None
    active_profile_id: Optional[int] = None


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

    nombre_perfil = usuario.perfil_jarvis or ""
    if usuario.active_profile_id:
        from backend.models import JarvisProfile
        jp = db.query(JarvisProfile).filter(JarvisProfile.id_perfil == usuario.active_profile_id).first()
        if jp:
            nombre_perfil = jp.nombre

    token = crear_token_jwt({
        "id_usuario": usuario.id_usuario,
        "id_tenant": usuario.id_tenant,
        "email": usuario.email,
        "perfil_jarvis": nombre_perfil,
        "rol": rol_usuario,
        "is_superadmin": rol_usuario in ROLS_STAFF,  # True para admin y superadmin
    })

    tenant = usuario.tenant
    return TokenResponse(
        access_token=token,
        perfil_jarvis=nombre_perfil,
        nombre_organizacion=tenant.nombre_organizacion if tenant else "N/A",
        rol=rol_usuario,
    )


# ---------------------------------------------------------------------------
# Dependencies de seguridad
# ---------------------------------------------------------------------------

security = HTTPBearer()


async def obtener_usuario_actual(
    credentials: HTTPAuthorizationCredentials = Depends(security),
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

    # Garantizar que el campo 'rol' siempre esté presente (tokens emitidos antes del RBAC)
    if "rol" not in payload:
        payload["rol"] = ROL_SUPERADMIN if payload.get("is_superadmin") else ROL_CLIENTE

    return payload


async def requiere_staff(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """
    Requiere rol 'superadmin' o 'admin'.
    Usado para proteger el panel de administración completo.
    """
    payload = await obtener_usuario_actual(credentials)
    if payload.get("rol") not in ROLS_STAFF:
        raise HTTPException(
            status_code=403,
            detail="Acceso denegado. Se requiere rol Admin o SuperAdmin.",
        )
    return payload


async def requiere_superadmin(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """
    Requiere específicamente rol 'superadmin'.
    Para operaciones solo del dueño del sistema (ej. gestionar otros admins).
    """
    payload = await obtener_usuario_actual(credentials)
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
    ) -> dict:
        payload = await obtener_usuario_actual(credentials)

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

    tenant = db.query(Tenant).filter(Tenant.id_tenant == user.id_tenant).first()
    if tenant:
        tenant.nombre_organizacion = data.nombre_organizacion
        if data.nombre_contacto is not None:
            tenant.nombre_contacto = data.nombre_contacto
        if data.telefono is not None:
            tenant.telefono = data.telefono

    if user.email != data.email:
        existing = db.query(Usuario).filter(Usuario.email == data.email).first()
        if existing:
            raise HTTPException(status_code=400, detail='El email ya está en uso')
        user.email = data.email

    if data.password:
        user.password_hash = bcrypt.hashpw(data.password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    if data.active_profile_id is not None:
        user.active_profile_id = data.active_profile_id

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
        'is_superadmin': user.rol in ROLS_STAFF if user.rol else user.is_superadmin,
        'active_profile_id': user.active_profile_id,
        'perfiles': perfiles,
        'plan_features': {
            'telegram': plan.permite_telegram if plan else False,
            'whatsapp': plan.permite_whatsapp if plan else False,
            'iot': plan.permite_iot if plan else False,
            'mikrotik': plan.permite_mikrotik if plan else False,
            'erp': plan.permite_erp if plan else False,
            'inspeccion': plan.permite_inspeccion if plan else False,
        }
    }
