from typing import Optional
"""
J.A.R.V.I.S. SaaS — Autenticación y Autorización

Correcciones aplicadas:
- Fix #6:  SECRET_KEY desde os.getenv("JWT_SECRET_KEY")
- Fix #7:  Endpoint POST /auth/login para obtener JWT
- Fix #8:  Captura específica de jwt.ExpiredSignatureError y jwt.InvalidTokenError
- Fix #9:  Validación de id_tenant en el payload del token
"""

import os
import datetime

import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import bcrypt
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Usuario

# ---------------------------------------------------------------------------
# Configuración (Fix #6: nunca hardcodear la secret key)
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
# Hashing de contraseñas (bcrypt directo, sin passlib)
# ---------------------------------------------------------------------------


def verificar_password(plain_password: str, hashed_password: str) -> bool:
    """Compara una contraseña en texto plano contra su hash bcrypt."""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


def hash_password(password: str) -> str:
    """Genera el hash bcrypt de una contraseña."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------

def crear_token_jwt(data: dict) -> str:
    """Genera un token JWT firmado con expiración."""
    payload = data.copy()
    payload["exp"] = datetime.datetime.utcnow() + datetime.timedelta(hours=TOKEN_EXPIRY_HOURS)
    payload["iat"] = datetime.datetime.utcnow()
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


# ---------------------------------------------------------------------------
# Schemas Pydantic
# ---------------------------------------------------------------------------


class ProfileUpdate(BaseModel):
    nombre_organizacion: str
    email: str
    password: Optional[str] = None

class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    perfil_jarvis: str
    nombre_organizacion: str


# ---------------------------------------------------------------------------
# Router de autenticación (Fix #7)
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/v1/auth", tags=["Autenticacion"])


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: Session = Depends(get_db)):
    """
    Autentica un usuario con email + contraseña y retorna un JWT.
    El token contiene: id_usuario, id_tenant, email, perfil_jarvis.
    """
    usuario = db.query(Usuario).filter(Usuario.email == body.email).first()

    if not usuario or not verificar_password(body.password, usuario.password_hash):
        raise HTTPException(status_code=401, detail="Credenciales inválidas.")

    token = crear_token_jwt({
        "id_usuario": usuario.id_usuario,
        "id_tenant": usuario.id_tenant,
        "email": usuario.email,
        "perfil_jarvis": usuario.perfil_jarvis,
    })

    tenant = usuario.tenant
    return TokenResponse(
        access_token=token,
        perfil_jarvis=usuario.perfil_jarvis,
        nombre_organizacion=tenant.nombre_organizacion if tenant else "N/A",
    )


# ---------------------------------------------------------------------------
# Dependencies de seguridad (Fix #8, #9)
# ---------------------------------------------------------------------------

security = HTTPBearer()


async def obtener_usuario_actual(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """
    Dependency de FastAPI: decodifica el JWT del header Authorization
    y retorna el payload como dict.

    Fix #8: captura excepciones JWT específicas.
    Fix #9: valida que id_tenant exista en el payload.
    """
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado. Inicie sesión nuevamente.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido.")

    # Fix #9: garantizar que el tenant esté presente
    if "id_usuario" not in payload or "id_tenant" not in payload:
        raise HTTPException(status_code=401, detail="Token con payload incompleto.")

    return payload


def requiere_feature(feature_requerido: str):
    """
    Factory de dependencia: retorna un callable que verifica que el usuario
    autenticado tenga acceso al módulo/feature solicitado según su perfil.

    Uso:
        @app.post("/endpoint")
        async def mi_endpoint(usuario: dict = Depends(requiere_feature("modulo_erp"))):
            ...
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
        perfil = payload.get("perfil_jarvis", "")

        perfiles_permitidos = PERMISOS.get(feature_requerido, [])
        if perfiles_permitidos and perfil not in perfiles_permitidos:
            raise HTTPException(
                status_code=403,
                detail=f"Acceso denegado. Perfil '{perfil}' no tiene permiso para '{feature_requerido}'.",
            )
        return payload

    return _verificar


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
        
    # Check if email is being changed and is already taken
    if user.email != data.email:
        existing = db.query(Usuario).filter(Usuario.email == data.email).first()
        if existing:
            raise HTTPException(status_code=400, detail='El email ya est en uso')
        user.email = data.email
        
    if data.password:
        import bcrypt
        user.password_hash = bcrypt.hashpw(data.password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
    db.commit()
    return {'message': 'Perfil actualizado correctamente'}


@router.get('/profile')
def get_profile(
    usuario: dict = Depends(obtener_usuario_actual),
    db: Session = Depends(get_db)
):
    from backend.models import Tenant
    user = db.query(Usuario).filter(Usuario.id_usuario == usuario['id_usuario']).first()
    if not user:
        raise HTTPException(status_code=404, detail='Usuario no encontrado')
        
    tenant = db.query(Tenant).filter(Tenant.id_tenant == user.id_tenant).first()
    
    return {
        'email': user.email,
        'nombre_organizacion': tenant.nombre_organizacion if tenant else ''
    }
