"""Canales Meta, bandeja omnicanal y contenido con aprobación humana."""
import os
import secrets
from urllib.parse import urlencode
from typing import Optional
from fastapi import APIRouter, Body, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from backend.auth import obtener_usuario_actual
from backend.crypto_utils import encrypt_secret, decrypt_secret
from backend.database import get_db
from backend.models import ChannelConnection, OmniConversation, OmniMessage, MarketingContent

router = APIRouter(prefix="/v1/marketing", tags=["Marketing y canales"])

WHATSAPP_GUIDE = [
    "Inicia sesión como administrador en Meta Business Manager.",
    "Confirma que tu empresa, número y nombre visible cumplen las políticas de Meta.",
    "Selecciona Conectar WhatsApp en Bonso: se abrirá el flujo oficial Embedded Signup.",
    "Autoriza solo WhatsApp Business Management y Messaging; nunca compartas contraseñas ni tokens por chat.",
    "Completa la prueba de número y verifica el mensaje de prueba desde la bandeja omnicanal.",
    "Configura plantillas, horario de atención, derivación a humano y reglas de respuesta antes de activar IA.",
]

class ConnectionPayload(BaseModel):
    provider: str = Field(pattern="^(whatsapp|instagram|messenger|facebook_ads)$")
    account_name: str = Field(min_length=2, max_length=255)
    external_account_id: Optional[str] = None
    phone_number_id: Optional[str] = None
    access_token: Optional[str] = None
    scopes: list[str] = []

class ContentPayload(BaseModel):
    title: str = Field(min_length=2, max_length=255)
    body: str = Field(min_length=2, max_length=10000)
    connection_id: Optional[str] = None

class ReplyPayload(BaseModel):
    content: str = Field(min_length=1, max_length=4096)
    send_now: bool = False

@router.get("/whatsapp-guide")
async def whatsapp_guide(usuario: dict = Depends(obtener_usuario_actual)):
    return {"title": "Conecta WhatsApp Business con Meta", "steps": WHATSAPP_GUIDE, "required_env": ["META_APP_ID", "META_APP_SECRET", "META_WEBHOOK_VERIFY_TOKEN"]}

@router.get("/connections")
async def connections(usuario: dict = Depends(obtener_usuario_actual), db: Session = Depends(get_db)):
    rows = db.query(ChannelConnection).filter(ChannelConnection.id_tenant == usuario["id_tenant"]).all()
    return [{"id_connection": row.id_connection, "provider": row.provider, "account_name": row.account_name, "status": row.status, "scopes": row.scopes, "created_at": row.created_at.isoformat() if row.created_at else None} for row in rows]

@router.post("/connections")
async def save_connection(body: ConnectionPayload, usuario: dict = Depends(obtener_usuario_actual), db: Session = Depends(get_db)):
    # El token se cifra; el cliente solo recibe el estado de conexión, jamás el secreto.
    row = ChannelConnection(id_tenant=usuario["id_tenant"], provider=body.provider, account_name=body.account_name, external_account_id=body.external_account_id, phone_number_id=body.phone_number_id, credential_encrypted=encrypt_secret(body.access_token) if body.access_token else None, scopes=body.scopes, status="pending_verification")
    db.add(row); db.commit(); db.refresh(row)
    return {"id_connection": row.id_connection, "status": row.status}


@router.post("/connections/meta/start/{provider}")
async def meta_oauth_start(provider: str, usuario: dict = Depends(obtener_usuario_actual), db: Session = Depends(get_db)):
    if provider not in {"instagram", "messenger", "facebook_ads"}: raise HTTPException(status_code=422, detail="Canal Meta no soportado")
    app_id = os.getenv("META_APP_ID", ""); redirect = os.getenv("META_OAUTH_REDIRECT_URL", "")
    if not app_id or not redirect: raise HTTPException(status_code=503, detail="OAuth de Meta aún no está configurado.")
    state = secrets.token_urlsafe(32)
    scopes = ["pages_show_list", "pages_read_engagement", "pages_manage_posts", "pages_messaging", "instagram_basic", "instagram_manage_messages", "instagram_content_publish", "ads_read"]
    row = ChannelConnection(id_tenant=usuario["id_tenant"], provider=provider, account_name=f"{provider} pendiente", status="oauth_pending", scopes=scopes, metadata_json={"oauth_state": state})
    db.add(row); db.commit()
    return {"authorization_url": "https://www.facebook.com/v21.0/dialog/oauth?" + urlencode({"client_id": app_id, "redirect_uri": redirect, "state": state, "scope": ",".join(scopes)})}


@router.get("/connections/meta/callback")
async def meta_oauth_callback(code: str, state: str, db: Session = Depends(get_db)):
    redirect = os.getenv("META_OAUTH_REDIRECT_URL", ""); app_id = os.getenv("META_APP_ID", ""); secret = os.getenv("META_APP_SECRET", "")
    row = next((item for item in db.query(ChannelConnection).filter(ChannelConnection.status == "oauth_pending").all() if (item.metadata_json or {}).get("oauth_state") == state), None)
    if not row or not redirect or not app_id or not secret: raise HTTPException(status_code=400, detail="Autorización inválida o expirada.")
    import httpx
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get("https://graph.facebook.com/v21.0/oauth/access_token", params={"client_id": app_id, "client_secret": secret, "redirect_uri": redirect, "code": code})
    if response.status_code >= 400: raise HTTPException(status_code=502, detail="Meta rechazó la autorización.")
    data = response.json(); row.credential_encrypted = encrypt_secret(data["access_token"]); row.status = "connected"; row.metadata_json = {"token_expires_in": data.get("expires_in")}; db.commit()
    return {"status": "connected", "message": "Cuenta Meta conectada. Puedes volver a Bonso."}

@router.get("/inbox")
async def inbox(usuario: dict = Depends(obtener_usuario_actual), db: Session = Depends(get_db)):
    rows = db.query(OmniConversation, ChannelConnection).join(ChannelConnection, OmniConversation.id_connection == ChannelConnection.id_connection).filter(OmniConversation.id_tenant == usuario["id_tenant"]).order_by(OmniConversation.last_message_at.desc()).limit(100).all()
    return [{"id_conversation": conv.id_conversation, "channel": channel.provider, "account": channel.account_name, "customer": conv.customer_name or conv.customer_external_id or "Cliente", "status": conv.status, "last_message_at": conv.last_message_at.isoformat() if conv.last_message_at else None} for conv, channel in rows]

@router.get("/inbox/{conversation_id}")
async def conversation(conversation_id: str, usuario: dict = Depends(obtener_usuario_actual), db: Session = Depends(get_db)):
    conv = db.query(OmniConversation).filter(OmniConversation.id_conversation == conversation_id, OmniConversation.id_tenant == usuario["id_tenant"]).first()
    if not conv: raise HTTPException(status_code=404, detail="Conversación no encontrada")
    return [{"id_message": msg.id_message, "direction": msg.direction, "content": msg.content, "ai_generated": msg.ai_generated, "status": msg.status, "created_at": msg.created_at.isoformat() if msg.created_at else None} for msg in db.query(OmniMessage).filter(OmniMessage.id_conversation == conv.id_conversation).order_by(OmniMessage.created_at).all()]

@router.post("/inbox/{conversation_id}/reply")
async def save_reply(conversation_id: str, body: ReplyPayload, usuario: dict = Depends(obtener_usuario_actual), db: Session = Depends(get_db)):
    conv = db.query(OmniConversation).filter(OmniConversation.id_conversation == conversation_id, OmniConversation.id_tenant == usuario["id_tenant"]).first()
    if not conv: raise HTTPException(status_code=404, detail="Conversación no encontrada")
    # El envío real se habilita por adaptador del canal después de la aprobación
    # de Meta; hasta entonces queda como borrador/auditable en la bandeja.
    msg = OmniMessage(id_conversation=conv.id_conversation, direction="outbound", content=body.content, ai_generated=False, status="queued" if body.send_now else "draft")
    db.add(msg); db.commit()
    return {"id_message": msg.id_message, "status": msg.status}

@router.get("/content")
async def list_content(usuario: dict = Depends(obtener_usuario_actual), db: Session = Depends(get_db)):
    return [{"id_content": item.id_content, "title": item.title, "body": item.body, "status": item.status, "scheduled_at": item.scheduled_at.isoformat() if item.scheduled_at else None} for item in db.query(MarketingContent).filter(MarketingContent.id_tenant == usuario["id_tenant"]).order_by(MarketingContent.created_at.desc()).limit(100).all()]

@router.post("/content")
async def create_content(body: ContentPayload, usuario: dict = Depends(obtener_usuario_actual), db: Session = Depends(get_db)):
    if body.connection_id and not db.query(ChannelConnection).filter(ChannelConnection.id_connection == body.connection_id, ChannelConnection.id_tenant == usuario["id_tenant"]).first(): raise HTTPException(status_code=404, detail="Canal no encontrado")
    item = MarketingContent(id_tenant=usuario["id_tenant"], id_connection=body.connection_id, title=body.title, body=body.body)
    db.add(item); db.commit(); db.refresh(item)
    return {"id_content": item.id_content, "status": item.status}

@router.post("/content/{content_id}/approve")
async def approve_content(content_id: str, usuario: dict = Depends(obtener_usuario_actual), db: Session = Depends(get_db)):
    item = db.query(MarketingContent).filter(MarketingContent.id_content == content_id, MarketingContent.id_tenant == usuario["id_tenant"]).first()
    if not item: raise HTTPException(status_code=404, detail="Contenido no encontrado")
    item.status = "approved"; item.approved_by = usuario["id_usuario"]; db.commit()
    return {"status": "approved"}
