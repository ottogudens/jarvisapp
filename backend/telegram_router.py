"""
J.A.R.V.I.S. Core Engine — Telegram Router & Integration APIs
"""
import os
import re
import httpx
import secrets
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Body, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.auth import obtener_usuario_actual
from backend.models import Usuario, ChatSession, ChatMessage
from backend.prompts import SYSTEM_PROMPTS

router = APIRouter(prefix="/v1/telegram", tags=["Telegram Integration"])
logger = logging.getLogger(__name__)

# Almacenamiento temporal en memoria de tokens de vinculación (token -> id_usuario)
_LINK_TOKENS = {}

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

class LinkTokenResponse(BaseModel):
    link_code: str
    bot_username: Optional[str] = None
    instructions: str

@router.get("/debug")
async def debug_telegram_webhook(usuario: dict = Depends(obtener_usuario_actual)):
    """Llama a getWebhookInfo para ver si Telegram detectó algún error de conectividad."""
    if not usuario.get("is_superadmin"):
         raise HTTPException(status_code=403, detail="Sin permisos.")
    if not TELEGRAM_BOT_TOKEN:
        return {"error": "Falta TELEGRAM_BOT_TOKEN"}
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{TELEGRAM_API_URL}/getWebhookInfo")
    return resp.json()

@router.post("/set-webhook")
async def set_telegram_webhook(
    request: Request,
    usuario: dict = Depends(obtener_usuario_actual)
):
    """Establece la URL del Webhook obteniéndola automáticamente de FastApi."""
    if not usuario.get("is_superadmin"):
        raise HTTPException(status_code=403, detail="No tienes permisos de superadmin para esto.")
        
    if not TELEGRAM_BOT_TOKEN:
        raise HTTPException(status_code=500, detail="Falta TELEGRAM_BOT_TOKEN en el entorno del servidor.")
        
    base_url = str(request.base_url).rstrip("/")
    # Railway redirige trafico a traves de HTTPS, hay que asegurar que usemos https://
    if "up.railway.app" in base_url and base_url.startswith("http://"):
        base_url = base_url.replace("http://", "https://")
        
    webhook_url = f"{base_url}/v1/telegram/webhook"
    
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{TELEGRAM_API_URL}/setWebhook",
            json={"url": webhook_url, "allowed_updates": ["message"]}
        )
    return {"webhook_url": webhook_url, "telegram_response": resp.json()}

@router.post("/link-code", response_model=LinkTokenResponse)
async def generar_codigo_vinculacion(
    usuario: dict = Depends(obtener_usuario_actual),
):
    """
    Genera un código de 6 dígitos temporal para vincular la cuenta web con Telegram.
    El usuario en Telegram enviará el código.
    """
    code = f"{secrets.randbelow(900000) + 100000}"
    _LINK_TOKENS[code] = usuario["id_usuario"]
    
    return LinkTokenResponse(
        link_code=code,
        instructions=f"Envía un mensaje con el código '{code}' a tu bot de Telegram para vincular tu cuenta."
    )

@router.get("/status")
async def consultar_estado_telegram(
    usuario: dict = Depends(obtener_usuario_actual),
    db: Session = Depends(get_db),
):
    """Obtiene el estado de conexión con Telegram del usuario actual."""
    user = db.query(Usuario).filter(Usuario.id_usuario == usuario["id_usuario"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    return {
        "connected": user.telegram_chat_id is not None,
        "telegram_chat_id": user.telegram_chat_id,
        "telegram_username": user.telegram_username,
    }

@router.post("/unlink")
async def desvincular_cuenta_telegram(
    usuario: dict = Depends(obtener_usuario_actual),
    db: Session = Depends(get_db),
):
    """Desvincula la cuenta de Telegram del usuario actual."""
    user = db.query(Usuario).filter(Usuario.id_usuario == usuario["id_usuario"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    user.telegram_chat_id = None
    user.telegram_username = None
    db.commit()
    return {"status": "success", "message": "Cuenta de Telegram desvinculada exitosamente"}

async def send_telegram_message(chat_id: str, text: str):
    if not TELEGRAM_BOT_TOKEN: return
    async with httpx.AsyncClient() as client:
        await client.post(
            f"{TELEGRAM_API_URL}/sendMessage",
            json={"chat_id": str(chat_id), "text": text, "parse_mode": "Markdown"}
        )

async def handle_link_code(db: Session, chat_id: str, username: str, text: str) -> bool:
    """Intenta capturar un código de vinculación en el mensaje de Telegram."""
    match = re.search(r'\b\d{6}\b', text)
    if not match: 
        return False
    
    code = match.group(0)
    id_usuario = _LINK_TOKENS.pop(code, None)
    if not id_usuario:
        # A code was sent but it is missing or expired, only inform if message was short (just the code)
        if len(text.strip()) <= 15:
            await send_telegram_message(chat_id, "❌ Código de vinculación inválido o expirado. Por favor genera uno nuevo en tu panel web.")
            return True
        return False # Was just 6 digits inside a bigger text
        
    user = db.query(Usuario).filter(Usuario.id_usuario == id_usuario).first()
    if not user:
        await send_telegram_message(chat_id, "❌ Error: Usuario no encontrado en la base de datos.")
        return True
        
    user.telegram_chat_id = int(chat_id)
    if username: 
        user.telegram_username = username
    db.commit()
    
    await send_telegram_message(
        chat_id, 
        f"✅ ¡Cuenta vinculada exitosamente con *{user.email}*!\n\nYa puedes enviarme consultas, comandos, fotos o notas de voz."
    )
    return True

@router.post("/webhook")
async def telegram_webhook(update: dict = Body(...), db: Session = Depends(get_db)):
    """Recepciona eventos nativos desde los servidores de Telegram (Webhook)."""
    if "message" not in update:
        return {"status": "ignored"}
        
    msg = update["message"]
    chat_id = str(msg["chat"]["id"])
    username = msg.get("from", {}).get("username") or msg.get("from", {}).get("first_name", "User")
    
    raw_text = msg.get("text", "")
    caption = msg.get("caption", "")
    text = raw_text or caption

    # Intentar vinculación
    if await handle_link_code(db, chat_id, username, text):
        return {"status": "ok"}

    # Validar que cuenta existiera
    user = db.query(Usuario).filter(Usuario.telegram_chat_id == chat_id).first()
    if not user:
        await send_telegram_message(
            chat_id, 
            "⚠️ Tu cuenta J.A.R.V.I.S. no está vinculada.\nGenera un código de 6 dígitos en tu panel web y envíalo por este medio para conectarnos."
        )
        return {"status": "ok"}

    file_url = None

    async def get_telegram_file_url(file_id: str) -> Optional[str]:
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{TELEGRAM_API_URL}/getFile", json={"file_id": file_id})
            if resp.status_code == 200:
                f_path = resp.json().get("result", {}).get("file_path")
                if f_path:
                    return f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{f_path}"
        return None

    # Procesar acción de tipeo/grabación
    async with httpx.AsyncClient() as client:
        if "voice" in msg:
            await client.post(f"{TELEGRAM_API_URL}/sendChatAction", json={"chat_id": chat_id, "action": "record_voice"})
            file_url = await get_telegram_file_url(msg["voice"]["file_id"])
            text = text or "Envié este archivo adjunto."
        elif "photo" in msg:
            await client.post(f"{TELEGRAM_API_URL}/sendChatAction", json={"chat_id": chat_id, "action": "upload_photo"})
            file_url = await get_telegram_file_url(msg["photo"][-1]["file_id"])
            text = text or "Describe qué ves en esta imagen adjunta."
        else:
            await client.post(f"{TELEGRAM_API_URL}/sendChatAction", json={"chat_id": chat_id, "action": "typing"})

    # Inyeccion de sesion de chat local en base de datos
    session = db.query(ChatSession).filter(
        ChatSession.id_usuario == user.id_usuario,
        ChatSession.titulo == "Telegram Chat"
    ).first()

    if not session:
        session = ChatSession(id_usuario=user.id_usuario, titulo="Telegram Chat")
        db.add(session)
        db.commit()
        db.refresh(session)

    perfil = user.perfil_jarvis or "Mecanico"
    sys_prompt = SYSTEM_PROMPTS.get(perfil, SYSTEM_PROMPTS["Mecanico"])

    # Obtener historial
    mensajes_previos = db.query(ChatMessage).filter(
        ChatMessage.id_session == session.id_session
    ).order_by(ChatMessage.created_at.desc()).limit(6).all()
    
    contexto_historial = ""
    for m in reversed(mensajes_previos):
        rol = "Usuario" if m.rol == "user" else "JARVIS"
        contexto_historial += f"{rol}: {m.contenido}\n"

    prompt_con_contexto = f"{contexto_historial}\nUsuario: {text}"
    uploaded_urls = [file_url] if file_url else []
    generated_urls = []
    
    # Procesar IA
    try:
        from backend.ai_service import call_llm_with_tools
        respuesta_jarvis, tokens = call_llm_with_tools(
            db=db,
            user_db=user,
            sys_prompt=sys_prompt,
            prompt_con_contexto=prompt_con_contexto,
            uploaded_urls=uploaded_urls,
            generated_urls=generated_urls
        )
    except Exception as e:
        logger.error(f"Error procesando LLM en Webhook: {e}")
        respuesta_jarvis = "❌ Tuve un error interno de inteligencia. Intenta de nuevo..."

    db.add(ChatMessage(id_session=session.id_session, rol="user", contenido=text, file_urls=uploaded_urls))
    db.add(ChatMessage(id_session=session.id_session, rol="jarvis", contenido=respuesta_jarvis, file_urls=generated_urls))
    db.commit()

    # Responder al usuario asincronamente
    await send_telegram_message(chat_id, respuesta_jarvis)

    return {"status": "ok"}
