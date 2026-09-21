"""
J.A.R.V.I.S. Core Engine — Telegram Router & Integration APIs (Multi-Tenant)
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
from backend.models import Usuario, ChatSession, ChatMessage, Tenant
from backend.prompts import SYSTEM_PROMPTS

router = APIRouter(prefix="/v1/telegram", tags=["Telegram Integration"])
logger = logging.getLogger(__name__)

# Almacenamiento temporal en memoria de tokens de vinculación (token -> id_usuario)
_LINK_TOKENS = {}

class LinkTokenResponse(BaseModel):
    link_code: str
    bot_username: Optional[str] = None
    instructions: str

class TelegramConfigPayload(BaseModel):
    bot_token: str

@router.post("/config", summary="Configurar el bot de Telegram del Tenant")
async def configurar_telegram_tenant(
    payload: TelegramConfigPayload,
    request: Request,
    usuario: dict = Depends(obtener_usuario_actual),
    db: Session = Depends(get_db)
):
    """Guarda el token de Telegram y registra automáticamente el Webhook dinámico."""
    tenant = db.query(Tenant).filter(Tenant.id_tenant == usuario["id_tenant"]).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Organización no encontrada")

    token = payload.bot_token.strip()
    
    base_url = str(request.base_url).rstrip("/")
    if "up.railway.app" in base_url and base_url.startswith("http://"):
        base_url = base_url.replace("http://", "https://")
        
    webhook_url = f"{base_url}/v1/telegram/webhook/{token}"
    
    api_url = f"https://api.telegram.org/bot{token}"
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{api_url}/setWebhook",
            json={"url": webhook_url, "allowed_updates": ["message"]}
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=400, detail="El token es inválido o Telegram rechazó el Webhook.")
            
    tenant.telegram_bot_token = token
    db.commit()
    
    return {"status": "success", "message": "Bot de Telegram configurado exitosamente", "webhook_url": webhook_url}

@router.delete("/config", summary="Desconectar el bot de Telegram del Tenant")
async def desconectar_telegram_tenant(
    usuario: dict = Depends(obtener_usuario_actual),
    db: Session = Depends(get_db)
):
    """Elimina el webhook en Telegram y borra el token del Tenant."""
    tenant = db.query(Tenant).filter(Tenant.id_tenant == usuario["id_tenant"]).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Organización no encontrada")

    if tenant.telegram_bot_token:
        # Intentar eliminar el webhook, ignorar si falla
        api_url = f"https://api.telegram.org/bot{tenant.telegram_bot_token}"
        try:
            async with httpx.AsyncClient() as client:
                await client.post(f"{api_url}/deleteWebhook")
        except Exception as e:
            logger.warning(f"No se pudo eliminar webhook de Telegram: {e}")

    tenant.telegram_bot_token = None
    db.commit()
    return {"status": "success", "message": "Bot de Telegram desconectado"}

@router.get("/debug")
async def debug_telegram_webhook(usuario: dict = Depends(obtener_usuario_actual), db: Session = Depends(get_db)):
    """Llama a getWebhookInfo para ver si Telegram detectó algún error de conectividad."""
    if not usuario.get("is_superadmin"):
         raise HTTPException(status_code=403, detail="Sin permisos.")
    tenant = db.query(Tenant).filter(Tenant.id_tenant == usuario["id_tenant"]).first()
    if not tenant or not tenant.telegram_bot_token:
        return {"error": "Falta el Bot Token del Tenant"}
    
    async with httpx.AsyncClient() as client:
        api_url = f"https://api.telegram.org/bot{tenant.telegram_bot_token}"
        resp = await client.get(f"{api_url}/getWebhookInfo")
    return resp.json()

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
        
    tenant = db.query(Tenant).filter(Tenant.id_tenant == user.id_tenant).first()
    
    return {
        "tenant_bot_configured": bool(tenant and tenant.telegram_bot_token),
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

async def send_telegram_message(bot_token: str, chat_id: str, text: str):
    if not bot_token: return
    api_url = f"https://api.telegram.org/bot{bot_token}"
    async with httpx.AsyncClient() as client:
        await client.post(
            f"{api_url}/sendMessage",
            json={"chat_id": str(chat_id), "text": text, "parse_mode": "Markdown"}
        )

async def send_telegram_document(bot_token: str, chat_id: str, filename: str, filebytes: bytes):
    if not bot_token: return
    api_url = f"https://api.telegram.org/bot{bot_token}"
    async with httpx.AsyncClient() as client:
        files = {'document': (filename, filebytes)}
        data = {'chat_id': str(chat_id)}
        await client.post(f"{api_url}/sendDocument", data=data, files=files)

async def handle_link_code(db: Session, bot_token: str, id_tenant: int, chat_id: str, username: str, text: str) -> bool:
    """Intenta capturar un código de vinculación en el mensaje de Telegram."""
    match = re.search(r'\b\d{6}\b', text)
    if not match: 
        return False
    
    code = match.group(0)
    id_usuario = _LINK_TOKENS.pop(code, None)
    if not id_usuario:
        if len(text.strip()) <= 15:
            await send_telegram_message(bot_token, chat_id, "❌ Código de vinculación inválido o expirado. Por favor genera uno nuevo en tu panel web.")
            return True
        return False 
        
    user = db.query(Usuario).filter(Usuario.id_usuario == id_usuario, Usuario.id_tenant == id_tenant).first()
    if not user:
        await send_telegram_message(bot_token, chat_id, "❌ Error: Usuario no encontrado en tu Organización.")
        return True
        
    user.telegram_chat_id = int(chat_id)
    if username: 
        user.telegram_username = username
    db.commit()
    
    await send_telegram_message(
        bot_token, chat_id, 
        f"✅ ¡Cuenta vinculada exitosamente con *{user.email}*!\n\nYa puedes enviarme consultas, comandos, fotos o notas de voz."
    )
    return True

@router.post("/webhook/{bot_token}")
async def telegram_webhook(bot_token: str, update: dict = Body(...), db: Session = Depends(get_db)):
    """Recepciona eventos nativos desde los servidores de Telegram (Webhook)."""
    if "message" not in update:
        return {"status": "ignored"}
        
    tenant = db.query(Tenant).filter(Tenant.telegram_bot_token == bot_token).first()
    if not tenant:
        return {"status": "ignored", "reason": "token not mapped"}
        
    msg = update["message"]
    chat_id = msg["chat"]["id"]
    username = msg.get("from", {}).get("username") or msg.get("from", {}).get("first_name", "User")
    
    raw_text = msg.get("text", "")
    caption = msg.get("caption", "")
    text = raw_text or caption

    # Intentar vinculación
    if await handle_link_code(db, bot_token, tenant.id_tenant, str(chat_id), username, text):
        return {"status": "ok"}

    # Validar que cuenta existiera
    user = db.query(Usuario).filter(Usuario.telegram_chat_id == chat_id, Usuario.id_tenant == tenant.id_tenant).first()
    if not user:
        await send_telegram_message(
            bot_token, str(chat_id), 
            "⚠️ Tu cuenta J.A.R.V.I.S. no está vinculada.\nGenera un código de 6 dígitos en tu panel web y envíalo por este medio para conectarnos."
        )
        return {"status": "ok"}

    file_url = None
    TELEGRAM_API_URL = f"https://api.telegram.org/bot{bot_token}"

    async def download_telegram_file(file_id: str) -> Optional[bytes]:
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{TELEGRAM_API_URL}/getFile", json={"file_id": file_id})
            if resp.status_code == 200:
                f_path = resp.json().get("result", {}).get("file_path")
                if f_path:
                    download_url = f"https://api.telegram.org/file/bot{bot_token}/{f_path}"
                    file_resp = await client.get(download_url)
                    if file_resp.status_code == 200:
                        return file_resp.content
        return None

    # Procesar acción de tipeo/grabación
    async with httpx.AsyncClient() as dict_client:
        if "voice" in msg or "audio" in msg:
            audio_source = msg.get("voice") or msg.get("audio")
            await dict_client.post(f"{TELEGRAM_API_URL}/sendChatAction", json={"chat_id": chat_id, "action": "record_voice"})
            audio_bytes = await download_telegram_file(audio_source["file_id"])
            
            if audio_bytes:
                from backend.ai_service import load_ai_keys
                import os, tempfile
                load_ai_keys(db)
                if os.getenv("OPENAI_API_KEY"):
                    try:
                        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tf:
                            tf.write(audio_bytes)
                            t_path = tf.name
                        
                        with open(t_path, "rb") as audio_file:
                            headers = {"Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}"}
                            files = {"file": ("audio.ogg", audio_file, "audio/ogg")}
                            res = await dict_client.post("https://api.openai.com/v1/audio/transcriptions", headers=headers, files=files, data={"model": "whisper-1"}, timeout=30.0)
                            
                            if res.status_code == 200:
                                trans = res.json().get("text", "")
                                text = (text + f" [Transcripción de mi nota de voz]: {trans}").strip()
                            else:
                                text = (text + " [Nota de voz recibida, error de transcripción en OpenAI]").strip()
                        os.unlink(t_path)
                    except Exception as e:
                        text = (text + " [Fallo al transcribir mi nota de voz]").strip()
                        logger.error(f"Error transcribiendo: {e}")
                else:
                    text = (text + " [Te he enviado una nota de voz pero tienes deshabilitado Whisper]").strip()
            
        elif "photo" in msg:
            await dict_client.post(f"{TELEGRAM_API_URL}/sendChatAction", json={"chat_id": chat_id, "action": "upload_photo"})
            photo_bytes = await download_telegram_file(msg["photo"][-1]["file_id"])
            if photo_bytes:
                import base64
                b64 = base64.b64encode(photo_bytes).decode("utf-8")
                file_url = f"data:image/jpeg;base64,{b64}"
            text = text or "Describe qué ves en esta imagen adjunta o atiende a mi consulta considerando lo que muestra."
            
        elif "document" in msg:
            await dict_client.post(f"{TELEGRAM_API_URL}/sendChatAction", json={"chat_id": chat_id, "action": "typing"})
            doc_obj = msg["document"]
            d_name = doc_obj.get("file_name", "archivo adjunto")
            mime_type = doc_obj.get("mime_type", "")
            
            doc_bytes = await download_telegram_file(doc_obj["file_id"])
            if doc_bytes:
                if "pdf" in mime_type.lower() or d_name.lower().endswith(".pdf"):
                    try:
                        import fitz  # PyMuPDF
                        import io
                        pdf_stream = io.BytesIO(doc_bytes)
                        doc_pdf = fitz.open(stream=pdf_stream, filetype="pdf")
                        texto_extraido = ""
                        for page in doc_pdf:
                            texto_extraido += page.get_text() + "\n"
                        doc_pdf.close()
                        
                        texto_extraido = texto_extraido.strip()
                        if len(texto_extraido) > 12000:
                            texto_extraido = texto_extraido[:12000] + "\n... [Resto del documento omitido por límite de memoria]"
                            
                        if texto_extraido:
                            text = (text + f"\n\n[El usuario adjuntó el documento PDF '{d_name}'. A continuación se encuentra el texto extraído del mismo para que lo analices:]\n\"\"\"\n{texto_extraido}\n\"\"\"").strip()
                            
                            # Auto-guardar en Base de Conocimiento del Agente
                            from backend.models import KnowledgeFolder, KnowledgeDocument, DocumentChunk
                            tenant = db.query(Tenant).filter(Tenant.id_tenant == user.id_tenant).first()
                            ai_provider = tenant.ai_provider if tenant else "openai"
                            from backend.ai_service import load_ai_keys
                            load_ai_keys(db)
                            
                            try:
                                carpeta_chat = db.query(KnowledgeFolder).filter(KnowledgeFolder.id_tenant == user.id_tenant, KnowledgeFolder.nombre == "Subidos por Telegram").first()
                                if not carpeta_chat:
                                    carpeta_chat = KnowledgeFolder(id_tenant=user.id_tenant, nombre="Subidos por Telegram")
                                    db.add(carpeta_chat)
                                    db.commit()
                                
                                nuevo_doc = KnowledgeDocument(id_tenant=user.id_tenant, id_usuario=user.id_usuario, id_folder=carpeta_chat.id_folder, nombre=d_name)
                                db.add(nuevo_doc)
                                db.commit()
                                
                                import textwrap
                                from litellm import embedding
                                partes = textwrap.wrap(texto_extraido, width=1000, replace_whitespace=False)
                                
                                emb_model = "text-embedding-3-small"
                                emb_kwargs = {}
                                if ai_provider.lower() == "gemini":
                                    emb_model = "gemini/text-embedding-004"
                                else:
                                    emb_kwargs["dimensions"] = 768
                                    
                                for idx, parte in enumerate(partes):
                                    emb_res = embedding(model=emb_model, input=[parte], **emb_kwargs)
                                    vector = emb_res.data[0]['embedding']
                                    chk = DocumentChunk(id_document=nuevo_doc.id_document, chunk_index=idx, texto=parte, embedding=vector)
                                    db.add(chk)
                                db.commit()
                                text += "\n[Aviso interno: Este documento fue guardado silenciosamente en tu Base de Conocimientos permanente bajo la carpeta 'Subidos por Telegram']."
                            except Exception as em_e:
                                db.rollback()
                                logger.error(f"Error guardando autoconocimiento de Telegram: {em_e}")
                                
                        else:
                            text = (text + f" [El usuario adjuntó el PDF '{d_name}', pero parece ser un documento escaneado sin texto seleccionable.]").strip()
                    except Exception as e:
                        logger.error(f"Error extrayendo PDF en Telegram: {e}")
                        text = (text + f" [He adjuntado el archivo {d_name}, pero ocurrió un fallo leyendo su contenido interno.]").strip()
                elif "text/" in mime_type.lower() or d_name.lower().endswith((".txt", ".md", ".csv")):
                    try:
                        texto_extraido = doc_bytes.decode("utf-8").strip()
                        if len(texto_extraido) > 12000:
                            texto_extraido = texto_extraido[:12000] + "\n... [Resto del archivo omitido por límite de memoria]"
                        text = (text + f"\n\n[El usuario adjuntó el archivo de texto '{d_name}'. A continuación su contenido:]\n{texto_extraido}").strip()
                    except Exception:
                        text = (text + f" [He adjuntado el archivo de texto '{d_name}', pero estaba codificado en un formato no legible.]").strip()
                else:
                    text = (text + f" [He adjuntado el archivo de formato no soportado nativamente: '{d_name}'. No es posible leer su contenido interno.]").strip()
            else:
                text = (text + f" [Intenté enviarte el archivo '{d_name}' pero falló su descarga.]").strip()
            
        else:
            await dict_client.post(f"{TELEGRAM_API_URL}/sendChatAction", json={"chat_id": chat_id, "action": "typing"})

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

    perfil = "Mecanico"
    sys_prompt = SYSTEM_PROMPTS.get("Mecanico", "")
    
    if user.active_profile_ids and len(user.active_profile_ids) > 0:
        from backend.models import JarvisProfile, TenantProfile
        first_profile = db.query(JarvisProfile).filter(JarvisProfile.id_perfil == user.active_profile_ids[0]).first()
        if first_profile:
            perfil = first_profile.nombre
            sys_prompt = first_profile.instrucciones_base or sys_prompt
            
            # Buscar instrucciones extra del Tenant
            tenant_profile = db.query(TenantProfile).filter(
                TenantProfile.id_perfil == first_profile.id_perfil,
                TenantProfile.id_tenant == user.id_tenant
            ).first()
            
            if tenant_profile and tenant_profile.instrucciones_extra:
                sys_prompt += f"\n\nInstrucciones Adicionales del Cliente:\n{tenant_profile.instrucciones_extra}"

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

    try:
        db.add(ChatMessage(id_session=session.id_session, rol="user", contenido=text, file_urls=uploaded_urls))
        db.add(ChatMessage(id_session=session.id_session, rol="jarvis", contenido=respuesta_jarvis, file_urls=generated_urls))
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Error crítico en base de datos de historial de chat de Telegram: {e}")

    # Responder al usuario asincronamente
    await send_telegram_message(bot_token, str(chat_id), respuesta_jarvis)
    
    # Enviar documentos generados adjuntos
    if generated_urls:
        import base64
        import urllib.parse
        for url in generated_urls:
            if url.startswith("data:"):
                try:
                    header, b64 = url.split("base64,", 1)
                    filebytes = base64.b64decode(b64)
                    
                    filename = "documento_jarvis.pdf"
                    if "name=" in header:
                        name_part = header.split("name=")[1].split(";")[0]
                        filename = urllib.parse.unquote(name_part)
                    elif "text/csv" in header: filename = "datos.csv"
                    elif "text/markdown" in header: filename = "informe.md"
                    
                    await send_telegram_document(bot_token, str(chat_id), filename, filebytes)
                except Exception as e:
                    logger.error(f"Error enviando documento por telegram: {e}")

    return {"status": "ok"}
