"""WhatsApp Meta → soporte guiado → Mikrowisp. Activación explícita por conexión."""
import hashlib
import hmac
import html
import json
import os
import re
import time
from urllib.parse import urlsplit

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import inspect

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.auth import obtener_usuario_actual
from backend.database import get_db
from backend.isp_support_flow import advance
from backend.models import ChannelConnection, ISPSupportSession, ISPSupportEvent, ROLS_STAFF

router = APIRouter(prefix='/v1/isp-support', tags=['Soporte ISP'])


def enabled_connection() -> str:
    connection_id = os.getenv('ISP_SUPPORT_CONNECTION_ID', '')
    if not connection_id:
        raise HTTPException(503, 'Soporte WhatsApp aún no activado.')
    return connection_id


def valid_signature(raw: bytes, signature: str, secret: str) -> bool:
    expected = 'sha256=' + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return bool(secret) and hmac.compare_digest(expected, signature)


def phone(value: str) -> str:
    result = value.lstrip('+')
    if not re.fullmatch(r'[1-9][0-9]{7,14}', result):
        raise HTTPException(422, 'Usa el teléfono internacional, sin espacios.')
    return result


def mikrowisp_configured() -> bool:
    try:
        url = urlsplit(os.getenv('MIKROWISP_BASE_URL', ''))
        return bool(url.scheme == 'https' and url.hostname and not url.username
                    and not url.password and not url.query and not url.fragment
                    and url.path.rstrip('/') == '/api/v1'
                    and os.getenv('MIKROWISP_API_TOKEN', '').strip())
    except ValueError:
        return False


def whatsapp_token(channel: ChannelConnection) -> str:
    """Exigir cifrado válido; no aceptar el fallback legado a texto plano."""
    key = os.getenv('APP_ENCRYPTION_KEY') or os.getenv('MIKROTIK_ENCRYPTION_KEY', '')
    try:
        token = Fernet(key.encode()).decrypt((channel.credential_encrypted or '').encode()).decode()
        if not token.strip():
            raise ValueError()
        return token
    except (ValueError, InvalidToken, UnicodeError, TypeError):
        raise HTTPException(503, 'Credencial WhatsApp cifrada inválida o clave no configurada.') from None


@router.get('/configuration')
def configuration(usuario: dict = Depends(obtener_usuario_actual), db: Session = Depends(get_db)):
    """Comprobación local: no llama a Meta/Mikrowisp ni revela valores secretos."""
    if usuario.get('rol') not in ROLS_STAFF:
        raise HTTPException(403, 'Solo un administrador puede revisar la configuración.')
    connection_id = os.getenv('ISP_SUPPORT_CONNECTION_ID', '')
    channel = None
    if connection_id:
        channel = db.query(ChannelConnection).filter_by(
            id_connection=connection_id, id_tenant=usuario['id_tenant'], provider='whatsapp').first()
        if not channel:
            raise HTTPException(404, 'Conexión WhatsApp no encontrada para este tenant.')
    encrypted_token = False
    if channel:
        try:
            whatsapp_token(channel)
            encrypted_token = True
        except HTTPException:
            pass
    tables = set(inspect(db.get_bind()).get_table_names())
    department = os.getenv('MIKROWISP_SUPPORT_DEPARTMENT', '1')
    checks = {
        'connection_selected': bool(channel),
        'support_tables': {'isp_support_sessions', 'isp_support_events'} <= tables,
        'meta_app_secret': bool(os.getenv('META_APP_SECRET', '').strip()),
        'meta_verify_token': bool(os.getenv('META_WEBHOOK_VERIFY_TOKEN', '').strip()),
        'meta_graph_version': bool(re.fullmatch(r'v\d+\.\d+', os.getenv('META_GRAPH_API_VERSION', ''))),
        'meta_phone_number': bool(channel and str(channel.phone_number_id or '').isdigit()),
        'meta_encrypted_token': encrypted_token,
        'mikrowisp_config': mikrowisp_configured(),
        'support_department': department.isascii() and department.isdigit() and int(department) > 0,
    }
    return {'configured': all(checks.values()), 'checks': checks,
            'external_connectivity': 'not_tested'}


async def mikrowisp(endpoint: str, payload: dict) -> dict:
    # No endpoints elegidos por el usuario o el modelo, ni redirects con token.
    if endpoint not in {'GetClientsDetails', 'NewTicket'}:
        raise ValueError('Endpoint no permitido')
    base = os.getenv('MIKROWISP_BASE_URL', '').rstrip('/')
    token = os.getenv('MIKROWISP_API_TOKEN', '')
    if not mikrowisp_configured():
        raise HTTPException(503, 'Mikrowisp aún no configurado.')
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
            response = await client.post(f'{base}/{endpoint}', json={**payload, 'token': token})
            response.raise_for_status()
            result = response.json()
        if not isinstance(result, dict) or result.get('estado') != 'exito':
            raise ValueError('Respuesta no exitosa')
        return result
    except (httpx.HTTPError, ValueError):
        # Nunca incorporar al error cuerpo upstream: puede contener secretos.
        raise HTTPException(502, 'No se pudo confirmar la operación con Mikrowisp.') from None


class Binding(BaseModel):
    customer_phone: str
    id_cliente: int = Field(gt=0)
    identity_verified: bool


@router.put('/bindings')
async def bind_customer(body: Binding, usuario: dict = Depends(obtener_usuario_actual), db: Session = Depends(get_db)):
    if usuario.get('rol') not in ROLS_STAFF:
        raise HTTPException(403, 'Solo un administrador puede verificar la vinculación.')
    connection_id = enabled_connection()
    channel = db.query(ChannelConnection).filter_by(id_connection=connection_id, id_tenant=usuario['id_tenant'], provider='whatsapp').first()
    if not channel or not body.identity_verified:
        raise HTTPException(422, 'Canal inválido o identidad aún no verificada por atención.')
    customer_phone = phone(body.customer_phone)
    result = await mikrowisp('GetClientsDetails', {'idcliente': body.id_cliente})
    matches = [item for item in result.get('datos', []) if str(item.get('id')) == str(body.id_cliente)]
    # El administrador verifica identidad fuera del chat; además debe coincidir
    # el móvil registrado. No basta conocer RUT o escribir un ID en WhatsApp.
    if len(matches) != 1 or re.sub(r'[^0-9]', '', str(matches[0].get('movil', ''))) != customer_phone:
        raise HTTPException(422, 'El móvil registrado no coincide; corrígelo en Mikrowisp antes de vincular.')
    row = db.query(ISPSupportSession).filter_by(id_connection=connection_id, customer_phone=customer_phone).first()
    if row and row.id_cliente != body.id_cliente:
        raise HTTPException(409, 'Número ya vinculado. Requiere revisión administrativa antes de reasignarlo.')
    if not row:
        row = ISPSupportSession(id_connection=connection_id, customer_phone=customer_phone, id_tenant=usuario['id_tenant'], id_cliente=body.id_cliente, verified_by=usuario['id_usuario'], state={})
        db.add(row)
    db.commit()
    return {'status': 'verified'}


@router.get('/webhook')
async def verify_webhook(request: Request):
    enabled_connection()
    query = request.query_params
    expected = os.getenv('META_WEBHOOK_VERIFY_TOKEN', '')
    if query.get('hub.mode') != 'subscribe' or not expected or not hmac.compare_digest(query.get('hub.verify_token', ''), expected):
        raise HTTPException(403, 'Verificación rechazada.')
    return PlainTextResponse(query.get('hub.challenge', ''))


async def send_text(channel: ChannelConnection, recipient: str, text: str):
    version = os.getenv('META_GRAPH_API_VERSION', '')
    if not re.fullmatch(r'v\d+\.\d+', version) or not channel.credential_encrypted or not str(channel.phone_number_id or '').isdigit():
        raise HTTPException(503, 'Falta configurar versión Graph, teléfono o credenciales de WhatsApp.')
    token = whatsapp_token(channel)
    async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
        response = await client.post(
            f'https://graph.facebook.com/{version}/{channel.phone_number_id}/messages',
            headers={'Authorization': f'Bearer {token}'},
            json={'messaging_product': 'whatsapp', 'to': recipient, 'type': 'text', 'text': {'body': text[:4096]}},
        )
    if response.status_code >= 300:
        raise HTTPException(502, 'No se confirmó el envío a WhatsApp.')


async def process_message(db: Session, channel: ChannelConnection, message: dict):
    message_id = message.get('id')
    recipient = message.get('from', '')
    if not isinstance(message_id, str) or not re.fullmatch(r'[1-9][0-9]{7,14}', recipient):
        return
    # No enviar texto libre por eventos antiguos o futuros/reproducidos.
    try:
        age = time.time() - int(message.get('timestamp', 0))
    except (TypeError, ValueError):
        return
    if not 0 <= age < 23 * 3600:
        return
    event = ISPSupportEvent(id_connection=channel.id_connection, message_id=message_id)
    db.add(event)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return  # Nunca repetir NewTicket ante reentregas de Meta.
    row = db.query(ISPSupportSession).filter_by(id_connection=channel.id_connection, customer_phone=recipient, id_tenant=channel.id_tenant).with_for_update().first()
    if not row:
        reply = 'Para consultar o abrir solicitudes, atención debe verificar y vincular tu número con tu cuenta. Contacta al canal habitual de atención de tu proveedor.'
    elif message.get('type') != 'text':
        reply = 'Por ahora el soporte guiado recibe texto. Escribe SOPORTE o TECNICO.'
    else:
        state, reply, create_ticket = advance(row.state, str((message.get('text') or {}).get('body', '')))
        row.state = state
        if create_ticket:
            # Reservar ANTES de la llamada externa. Un timeout puede haber creado
            # el ticket: no reintentar automáticamente ni permitir otro al reiniciar.
            db.commit()
            details = html.escape(state['problem']) + '<br>' + html.escape('; '.join(state.get('checks', [])))
            try:
                result = await mikrowisp('NewTicket', {
                    'idcliente': row.id_cliente, 'dp': int(os.getenv('MIKROWISP_SUPPORT_DEPARTMENT', '1')),
                    'asunto': 'Solicitud de soporte desde WhatsApp', 'contenido': details + '<br>Fecha y turno solicitados; visita pendiente de confirmación.',
                    'fechavisita': state['date'], 'turno': state['shift'], 'agendado': 'RED SOCIAL',
                })
                ticket_id = result.get('idticket')
                if not str(ticket_id or '').isdigit():
                    raise HTTPException(502, 'Respuesta de ticket sin identificador.')
                row.state = {**state, 'stage': 'done', 'ticket_id': str(ticket_id)}
                reply = f'Ticket {ticket_id} registrado. El equipo revisará tu solicitud; la visita y su horario aún no están confirmados.'
            except (HTTPException, ValueError):
                row.state = {**state, 'stage': 'unknown'}
                reply = 'No pudimos confirmar el número de ticket. Atención debe revisar el registro antes de intentar nuevamente, para evitar duplicados.'
    event.status = 'sending'
    db.commit()
    try:
        await send_text(channel, recipient, reply)
        event.status = 'sent'
    except (HTTPException, httpx.HTTPError):
        event.status = 'delivery_unknown'
    db.commit()


@router.post('/webhook')
async def webhook(request: Request, db: Session = Depends(get_db)):
    connection_id = enabled_connection()
    raw = await request.body()
    if len(raw) > 1024 * 1024:
        raise HTTPException(413, 'Evento demasiado grande.')
    if not valid_signature(raw, request.headers.get('x-hub-signature-256', ''), os.getenv('META_APP_SECRET', '')):
        raise HTTPException(403, 'Firma inválida.')
    try:
        payload = json.loads(raw)
    except ValueError:
        raise HTTPException(400, 'JSON inválido.') from None
    if not isinstance(payload, dict) or payload.get('object') != 'whatsapp_business_account':
        return {'status': 'ignored'}
    channel = db.query(ChannelConnection).filter_by(id_connection=connection_id, provider='whatsapp').first()
    if not channel or not channel.credential_encrypted:
        raise HTTPException(503, 'Conexión WhatsApp no configurada.')
    for entry in payload.get('entry', []):
        for change in entry.get('changes', []):
            value = change.get('value') or {}
            if change.get('field') != 'messages' or str((value.get('metadata') or {}).get('phone_number_id')) != channel.phone_number_id:
                continue
            for message in value.get('messages', []):
                await process_message(db, channel, message)
    return {'status': 'processed'}


class ReviewResolution(BaseModel):
    customer_phone: str
    checked_in_mikrowisp: bool
    review_note: str = Field(min_length=10, max_length=1000)


@router.post('/review-and-reset')
async def review_and_reset(body: ReviewResolution, usuario: dict = Depends(obtener_usuario_actual), db: Session = Depends(get_db)):
    """Reabrir flujo solo tras revisión humana, también ante resultado ambiguo."""
    if usuario.get('rol') not in ROLS_STAFF or not body.checked_in_mikrowisp:
        raise HTTPException(403, 'Un administrador debe revisar previamente el registro en Mikrowisp.')
    row = db.query(ISPSupportSession).filter_by(id_connection=enabled_connection(), customer_phone=phone(body.customer_phone), id_tenant=usuario['id_tenant']).with_for_update().first()
    if not row:
        raise HTTPException(404, 'Vinculación no encontrada.')
    previous = dict(row.state or {})
    history = previous.pop('reviews', [])[-9:]
    row.state = {'stage': 'start', 'reviews': history + [{'by': usuario['id_usuario'], 'at': int(time.time()), 'note': body.review_note, 'previous': previous}]}
    db.commit()
    return {'status': 'reset_after_review'}
