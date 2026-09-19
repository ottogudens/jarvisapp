"""
J.A.R.V.I.S. Core Engine — Telegram Router & Integration APIs
"""
import uuid
import secrets
import base64
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.auth import obtener_usuario_actual
from backend.models import Usuario, ChatSession, ChatMessage
from backend.ai_service import call_llm_with_tools
from backend.prompts import SYSTEM_PROMPTS

router = APIRouter(prefix="/v1/telegram", tags=["Telegram Integration"])

# Almacenamiento temporal en memoria de tokens de vinculación (token -> id_usuario)
_LINK_TOKENS = {}

class LinkTokenResponse(BaseModel):
    link_code: str
    bot_username: Optional[str] = None
    instructions: str

class ProcessTelegramMessageRequest(BaseModel):
    telegram_chat_id: str
    telegram_username: Optional[str] = None
    text: Optional[str] = ""
    audio_b64: Optional[str] = None
    file_url: Optional[str] = None

class LinkAccountRequest(BaseModel):
    telegram_chat_id: str
    telegram_username: Optional[str] = None
    link_code: str

@router.post("/link-code", response_model=LinkTokenResponse)
async def generar_codigo_vinculacion(
    usuario: dict = Depends(obtener_usuario_actual),
):
    """
    Genera un código de 6 dígitos temporal para vincular la cuenta web con Telegram.
    El usuario en Telegram enviará `/start <codigo>`.
    """
    code = f"{secrets.randbelow(900000) + 100000}"
    _LINK_TOKENS[code] = usuario["id_usuario"]
    
    return LinkTokenResponse(
        link_code=code,
        instructions=f"Envía el comando '/start {code}' a tu bot de Telegram para vincular tu cuenta."
    )

@router.post("/link-account")
async def vincular_cuenta_telegram(
    body: LinkAccountRequest,
    db: Session = Depends(get_db),
):
    """
    Utilizado por la instancia del bot de Telegram para validar el código enviado por el usuario.
    """
    id_usuario = _LINK_TOKENS.pop(body.link_code, None)
    if not id_usuario:
        raise HTTPException(status_code=400, detail="Código de vinculación inválido o expirado.")
    
    user = db.query(Usuario).filter(Usuario.id_usuario == id_usuario).first()
    if not user:
        raise HTTPException(status_code=4404, detail="Usuario no encontrado.")
    
    user.telegram_chat_id = body.telegram_chat_id
    if body.telegram_username:
        user.telegram_username = body.telegram_username
        
    db.commit()
    return {
        "status": "success",
        "message": f"Cuenta vinculada exitosamente con el correo {user.email}",
        "email": user.email
    }

@router.post("/process-message")
async def procesar_mensaje_telegram(
    body: ProcessTelegramMessageRequest,
    db: Session = Depends(get_db),
):
    """
    Procesa un mensaje enviado desde la instancia del bot de Telegram.
    Busca al usuario vinculado por telegram_chat_id y ejecuta el pipeline de IA con sus herramientas.
    """
    user = db.query(Usuario).filter(Usuario.telegram_chat_id == body.telegram_chat_id).first()
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Tu cuenta de Telegram no está vinculada a ningún usuario en J.A.R.V.I.S. Por favor vincula tu cuenta primero con /start <codigo>."
        )

    # Buscar o crear sesión de chat para Telegram
    session = db.query(ChatSession).filter(
        ChatSession.id_usuario == user.id_usuario,
        ChatSession.titulo == "Telegram Chat"
    ).first()

    if not session:
        session = ChatSession(
            id_usuario=user.id_usuario,
            titulo="Telegram Chat"
        )
        db.add(session)
        db.commit()
        db.refresh(session)

    # Si hay audio b64 enviado, usar STT primero o enviarlo al pipeline multimodal
    prompt_usuario = body.text or "Analiza la entrada adjunta."
    uploaded_urls = []
    if body.file_url:
        uploaded_urls.append(body.file_url)

    # Determinar prompt según perfil del usuario
    perfil = user.perfil_jarvis or "Mecanico"
    sys_prompt = SYSTEM_PROMPTS.get(perfil, SYSTEM_PROMPTS["Mecanico"])

    # Historial reciente de conversación
    mensajes_previos = db.query(ChatMessage).filter(
        ChatMessage.id_session == session.id_session
    ).order_by(ChatMessage.created_at.desc()).limit(6).all()
    
    contexto_historial = ""
    for m in reversed(mensajes_previos):
        rol = "Usuario" if m.rol == "user" else "JARVIS"
        contexto_historial += f"{rol}: {m.contenido}\n"

    prompt_con_contexto = f"{contexto_historial}\nUsuario: {prompt_usuario}"

    generated_urls = []
    
    # Invocar el pipeline con herramientas (MikroTik, IoT, RAG, etc.)
    respuesta_jarvis, tokens = call_llm_with_tools(
        db=db,
        user_db=user,
        sys_prompt=sys_prompt,
        prompt_con_contexto=prompt_con_contexto,
        uploaded_urls=uploaded_urls,
        generated_urls=generated_urls,
    )

    # Guardar mensajes en BD
    msg_user = ChatMessage(
        id_session=session.id_session,
        rol="user",
        contenido=prompt_usuario,
        file_urls=uploaded_urls
    )
    msg_jarvis = ChatMessage(
        id_session=session.id_session,
        rol="jarvis",
        contenido=respuesta_jarvis,
        file_urls=generated_urls
    )
    db.add(msg_user)
    db.add(msg_jarvis)
    db.commit()

    return {
        "status": "success",
        "respuesta": respuesta_jarvis,
        "generated_urls": generated_urls,
        "tokens_consumidos": tokens
    }
