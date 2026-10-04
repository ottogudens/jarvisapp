"""Facturación SaaS con Mercado Pago: checkout, consulta y webhook verificable."""
import hashlib
import hmac
import os
import secrets
from typing import Optional

import httpx
from fastapi import APIRouter, Body, Depends, Header, HTTPException, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.auth import obtener_usuario_actual
from backend.database import get_db
from backend.models import AIUsageStats, BillingSubscription, SaaSPlan, Tenant, Usuario
from backend.trial_policy import trial_snapshot

router = APIRouter(prefix="/v1/billing", tags=["Facturación"])
MP_API = "https://api.mercadopago.com"


def _mp_token() -> str:
    token = os.getenv("MP_ACCESS_TOKEN", "").strip()
    if not token:
        raise HTTPException(status_code=503, detail="Mercado Pago aún no está configurado para cobros.")
    return token


@router.get("/status")
async def billing_status(usuario: dict = Depends(obtener_usuario_actual), db: Session = Depends(get_db)):
    tenant = db.query(Tenant).filter(Tenant.id_tenant == usuario["id_tenant"]).first()
    plan = tenant.plan if tenant else None
    subscription = db.query(BillingSubscription).filter(
        BillingSubscription.id_tenant == usuario["id_tenant"]
    ).order_by(BillingSubscription.updated_at.desc()).first()
    usage = sum((item.tokens_consumidos or 0) for item in db.query(Usuario).filter(Usuario.id_tenant == usuario["id_tenant"]).all())
    daily_usage = db.query(func.coalesce(func.sum(AIUsageStats.tokens_consumidos), 0)).filter(
        AIUsageStats.id_tenant == usuario["id_tenant"],
        func.date(AIUsageStats.fecha_registro) == func.current_date(),
    ).scalar() or 0
    trial = trial_snapshot(tenant, daily_usage) if tenant else {}
    return {
        "plan": plan.nombre_plan if plan else "Sin plan", "tokens_mensuales": plan.tokens_mensuales if plan else 0,
        "tokens_consumidos": usage, "precio_mensual": plan.precio_mensual if plan else 0,
        "moneda": plan.moneda if plan else "CLP", "subscription_status": subscription.status if subscription else "none",
        "checkout_url": subscription.checkout_url if subscription and subscription.status in {"pending", "paused"} else None,
        "trial": trial,
    }


@router.get("/plans")
async def billing_plans(usuario: dict = Depends(obtener_usuario_actual), db: Session = Depends(get_db)):
    return [{"id_plan": p.id_plan, "nombre": p.nombre_plan, "precio_mensual": p.precio_mensual, "moneda": p.moneda, "tokens_mensuales": p.tokens_mensuales} for p in db.query(SaaSPlan).order_by(SaaSPlan.precio_mensual).all()]


@router.post("/checkout/{plan_id}")
async def create_checkout(plan_id: int, request: Request, usuario: dict = Depends(obtener_usuario_actual), db: Session = Depends(get_db)):
    plan = db.query(SaaSPlan).filter(SaaSPlan.id_plan == plan_id).first()
    tenant = db.query(Tenant).filter(Tenant.id_tenant == usuario["id_tenant"]).first()
    user = db.query(Usuario).filter(Usuario.id_usuario == usuario["id_usuario"]).first()
    if not plan or not tenant or not user: raise HTTPException(status_code=404, detail="Plan u organización no encontrada.")
    if plan.precio_mensual <= 0: raise HTTPException(status_code=422, detail="Este plan no tiene un precio configurado.")
    token = _mp_token()
    back_url = os.getenv("MP_BACK_URL", str(request.base_url).rstrip("/")).rstrip("/")
    payload = {
        "reason": f"Bonso · {plan.nombre_plan}", "payer_email": user.email,
        "auto_recurring": {"frequency": 1, "frequency_type": "months", "transaction_amount": plan.precio_mensual, "currency_id": plan.moneda},
        "back_url": back_url, "external_reference": f"tenant:{tenant.id_tenant}:plan:{plan.id_plan}",
        "status": "pending",
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(f"{MP_API}/preapproval", headers={"Authorization": f"Bearer {token}"}, json=payload)
    if response.status_code >= 400: raise HTTPException(status_code=502, detail="Mercado Pago no pudo crear la suscripción.")
    data = response.json()
    subscription = BillingSubscription(id_tenant=tenant.id_tenant, id_plan=plan.id_plan, provider_subscription_id=data.get("id"), status=data.get("status", "pending"), amount=plan.precio_mensual, currency=plan.moneda, checkout_url=data.get("init_point"), raw_status=data)
    db.add(subscription); db.commit()
    return {"checkout_url": subscription.checkout_url, "subscription_id": subscription.id_subscription}


@router.post("/webhook")
async def mercado_pago_webhook(request: Request, payload: dict = Body(default={}), x_signature: Optional[str] = Header(None), x_request_id: Optional[str] = Header(None), db: Session = Depends(get_db)):
    secret = os.getenv("MP_WEBHOOK_SECRET", "")
    if not secret: raise HTTPException(status_code=503, detail="Webhook de pagos no configurado.")
    event_id = str((payload.get("data") or {}).get("id") or request.query_params.get("data.id") or "")
    parts = dict(item.split("=", 1) for item in (x_signature or "").split(",") if "=" in item)
    manifest = f"id:{event_id};request-id:{x_request_id or ''};ts:{parts.get('ts', '')};"
    expected = hmac.new(secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()
    if not event_id or not hmac.compare_digest(expected, parts.get("v1", "")): raise HTTPException(status_code=401, detail="Firma de webhook inválida.")
    token = _mp_token()
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(f"{MP_API}/preapproval/{event_id}", headers={"Authorization": f"Bearer {token}"})
    if response.status_code >= 400: raise HTTPException(status_code=502, detail="No se pudo consultar el cobro.")
    data = response.json()
    subscription = db.query(BillingSubscription).filter(BillingSubscription.provider_subscription_id == event_id).first()
    if subscription:
        subscription.status = data.get("status", subscription.status); subscription.raw_status = data; db.commit()
    return {"status": "ok"}
