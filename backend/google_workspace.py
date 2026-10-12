"""OAuth de Google Workspace para Gmail y Calendar por tenant."""
import json
import os
import secrets
from datetime import datetime, timezone
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.auth import obtener_usuario_actual
from backend.crypto_utils import encrypt_secret
from backend.database import get_db
from backend.models import ChannelConnection, Tenant

router = APIRouter(prefix="/v1/google-workspace", tags=["Google Workspace"])

GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar.events",
]


def _check_integration_quota(db: Session, tenant_id: int) -> None:
    tenant = db.query(Tenant).filter(Tenant.id_tenant == tenant_id).first()
    limit = tenant.plan.max_integraciones if tenant and tenant.plan else 0
    if limit <= 0:
        return
    existing = db.query(ChannelConnection).filter(ChannelConnection.id_tenant == tenant_id, ChannelConnection.provider == "google_workspace", ChannelConnection.status.in_(("connected", "oauth_pending", "pending_verification"))).first()
    used = db.query(ChannelConnection.provider).filter(ChannelConnection.id_tenant == tenant_id, ChannelConnection.status.in_(("connected", "oauth_pending", "pending_verification"))).distinct().count()
    if not existing and used >= limit:
        raise HTTPException(status_code=403, detail=f"Tu plan permite un máximo de {limit} integraciones. Desconecta una integración o mejora tu plan.")


def _config() -> tuple[str, str, str]:
    client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "")
    client_secret = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "")
    redirect_url = os.getenv("GOOGLE_OAUTH_REDIRECT_URL", "")
    if not client_id or not client_secret or not redirect_url:
        raise HTTPException(status_code=503, detail="Google Workspace aún no está configurado. Falta configurar las credenciales OAuth del servidor.")
    return client_id, client_secret, redirect_url


@router.get("/status")
async def status_google_workspace(usuario: dict = Depends(obtener_usuario_actual), db: Session = Depends(get_db)):
    row = db.query(ChannelConnection).filter(
        ChannelConnection.id_tenant == usuario["id_tenant"],
        ChannelConnection.provider == "google_workspace",
    ).order_by(ChannelConnection.updated_at.desc()).first()
    if not row:
        return {"connected": False, "account_name": None, "scopes": []}
    return {"connected": row.status == "connected", "account_name": row.account_name if row.status == "connected" else None, "scopes": row.scopes or []}


@router.post("/start")
async def iniciar_google_workspace(usuario: dict = Depends(obtener_usuario_actual), db: Session = Depends(get_db)):
    _check_integration_quota(db, usuario["id_tenant"])
    client_id, _, redirect_url = _config()
    state = secrets.token_urlsafe(32)
    row = ChannelConnection(
        id_tenant=usuario["id_tenant"],
        provider="google_workspace",
        account_name="Cuenta Google pendiente",
        status="oauth_pending",
        scopes=GOOGLE_SCOPES,
        metadata_json={"oauth_state": state},
    )
    db.add(row)
    db.commit()
    return {
        "authorization_url": "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode({
            "client_id": client_id,
            "redirect_uri": redirect_url,
            "response_type": "code",
            "scope": " ".join(GOOGLE_SCOPES),
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        })
    }


@router.get("/callback")
async def callback_google_workspace(code: str, state: str, db: Session = Depends(get_db)):
    client_id, client_secret, redirect_url = _config()
    row = next((item for item in db.query(ChannelConnection).filter(
        ChannelConnection.provider == "google_workspace",
        ChannelConnection.status == "oauth_pending",
    ).all() if (item.metadata_json or {}).get("oauth_state") == state), None)
    if not row:
        raise HTTPException(status_code=400, detail="Autorización inválida o expirada.")
    async with httpx.AsyncClient(timeout=20.0) as client:
        token_response = await client.post("https://oauth2.googleapis.com/token", data={
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_url,
            "grant_type": "authorization_code",
        })
        if token_response.status_code >= 400:
            raise HTTPException(status_code=502, detail="Google rechazó la autorización.")
        tokens = token_response.json()
        user_response = await client.get("https://www.googleapis.com/oauth2/v3/userinfo", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    user = user_response.json() if user_response.status_code < 400 else {}
    row.account_name = user.get("email") or "Cuenta Google conectada"
    row.credential_encrypted = encrypt_secret(json.dumps({
        "access_token": tokens.get("access_token"),
        "refresh_token": tokens.get("refresh_token"),
        "expires_in": tokens.get("expires_in"),
    }))
    row.status = "connected"
    row.metadata_json = {"connected_at": datetime.now(timezone.utc).isoformat(), "email": user.get("email")}
    db.commit()
    return {"status": "connected", "message": "Gmail y Google Calendar quedaron conectados. Puedes volver a Bonso."}
