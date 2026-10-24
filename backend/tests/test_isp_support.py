import asyncio
import hashlib
import hmac
import os
import time
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock

os.environ.setdefault('DATABASE_URL', 'postgresql://test:test@localhost/test')
os.environ.setdefault('JWT_SECRET_KEY', 'unit-test-only')

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from backend import isp_support as support
from backend.isp_support_flow import advance
from backend.models import ISPSupportEvent, ISPSupportSession


def test_guide_escalates_los_and_requires_confirmation():
    state, _, _ = advance({}, 'soporte')
    for answer in ['TODOS', 'SI', 'SI', 'Sin conexión desde ayer']:
        state, _, create = advance(state, answer)
        assert not create
    assert state['stage'] == 'date'
    state, _, _ = advance(state, '2026-10-24', date(2026, 10, 23))
    state, reply, _ = advance(state, 'mañana')
    assert 'sin confirmar' in reply
    assert not advance(state, 'sí')[2]
    assert advance(state, 'CONFIRMAR')[2]


def test_invalid_dates_cancel_and_unknown_do_not_create():
    for value in ['2026-10-22', '2027-01-01', 'mañana', '2026-99-99']:
        assert advance({'stage': 'date'}, value, date(2026, 10, 23))[0]['stage'] == 'date'
    assert advance({'stage': 'date'}, 'cancelar')[0] == {'stage': 'start'}
    for stage in ['unknown', 'submitting']:
        assert not advance({'stage': stage}, 'CONFIRMAR')[2]
        assert advance({'stage': stage}, 'CANCELAR')[0]['stage'] == stage


def test_signature_rejects_modified_payload_and_missing_secret():
    raw = b'{"test":1}'
    signature = 'sha256=' + hmac.new(b'secret', raw, hashlib.sha256).hexdigest()
    assert support.valid_signature(raw, signature, 'secret')
    assert not support.valid_signature(raw + b' ', signature, 'secret')
    assert not support.valid_signature(raw, signature, '')


@pytest.fixture
def db():
    engine = create_engine('sqlite://')
    ISPSupportSession.__table__.create(engine)
    ISPSupportEvent.__table__.create(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def channel():
    return SimpleNamespace(id_connection='channel1', id_tenant=4)


def message(mid='m1', text='CONFIRMAR'):
    return {'id': mid, 'from': '56912345678', 'type': 'text', 'timestamp': str(int(time.time())), 'text': {'body': text}}


def seed(db):
    db.add(ISPSupportSession(id_connection='channel1', customer_phone='56912345678', id_tenant=4, id_cliente=33, verified_by=1,
        state={'stage': 'confirm', 'problem': '<script>sin red</script>', 'checks': ['LOS roja'], 'date': '2026-10-24', 'shift': 'TARDE'}))
    db.commit()


def test_duplicate_meta_message_creates_only_one_ticket(db, monkeypatch):
    seed(db)
    api = AsyncMock(return_value={'estado': 'exito', 'idticket': '100'})
    sender = AsyncMock()
    monkeypatch.setattr(support, 'mikrowisp', api)
    monkeypatch.setattr(support, 'send_text', sender)
    asyncio.run(support.process_message(db, channel(), message()))
    asyncio.run(support.process_message(db, channel(), message()))
    asyncio.run(support.process_message(db, channel(), message('m2')))
    assert api.await_count == 1
    assert '&lt;script&gt;' in api.call_args.args[1]['contenido']
    assert db.query(ISPSupportSession).one().state['ticket_id'] == '100'


def test_ambiguous_timeout_blocks_new_ticket_even_after_cancel(db, monkeypatch):
    seed(db)
    api = AsyncMock(side_effect=HTTPException(502, 'timeout'))
    monkeypatch.setattr(support, 'mikrowisp', api)
    monkeypatch.setattr(support, 'send_text', AsyncMock())
    for mid, text in [('m1', 'CONFIRMAR'), ('m2', 'CANCELAR'), ('m3', 'CONFIRMAR')]:
        asyncio.run(support.process_message(db, channel(), message(mid, text)))
    assert api.await_count == 1
    assert db.query(ISPSupportSession).one().state['stage'] == 'unknown'


def test_unverified_or_other_tenant_cannot_create_ticket(db, monkeypatch):
    seed(db)
    api = AsyncMock()
    monkeypatch.setattr(support, 'mikrowisp', api)
    monkeypatch.setattr(support, 'send_text', AsyncMock())
    other = SimpleNamespace(id_connection='channel1', id_tenant=5)
    asyncio.run(support.process_message(db, other, message()))
    assert api.await_count == 0


def test_stale_message_does_not_send_or_create(db, monkeypatch):
    seed(db)
    api = AsyncMock()
    sender = AsyncMock()
    monkeypatch.setattr(support, 'mikrowisp', api)
    monkeypatch.setattr(support, 'send_text', sender)
    stale = {**message(), 'timestamp': str(int(time.time()) - 24 * 3600)}
    asyncio.run(support.process_message(db, channel(), stale))
    assert api.await_count == sender.await_count == 0


def test_recovered_connection_does_not_open_ticket():
    state = {'stage': 'step', 'step': 3, 'checks': []}
    result, reply, create = advance(state, 'SI')
    assert not create
    assert result['stage'] == 'start'
    assert 'No se ha creado un ticket' in reply


def test_binding_requires_staff_and_explicit_identity_check(db, monkeypatch):
    api = AsyncMock()
    monkeypatch.setattr(support, 'mikrowisp', api)
    body = support.Binding(customer_phone='56912345678', id_cliente=33, identity_verified=True)
    with pytest.raises(HTTPException) as error:
        asyncio.run(support.bind_customer(body, {'rol': 'cliente', 'id_tenant': 4}, db))
    assert error.value.status_code == 403
    assert api.await_count == 0


def test_review_cannot_reset_another_tenants_session(db, monkeypatch):
    seed(db)
    monkeypatch.setenv('ISP_SUPPORT_CONNECTION_ID', 'channel1')
    body = support.ReviewResolution(customer_phone='56912345678', checked_in_mikrowisp=True, review_note='Revisión administrativa completada')
    with pytest.raises(HTTPException) as error:
        asyncio.run(support.review_and_reset(body, {'rol': 'admin', 'id_tenant': 5, 'id_usuario': 2}, db))
    assert error.value.status_code == 404
    assert db.query(ISPSupportSession).one().state['stage'] == 'confirm'


def test_review_history_survives_new_guide_and_cancel():
    state = {'stage': 'start', 'reviews': [{'note': 'Revisado manualmente'}]}
    state, _, _ = advance(state, 'SOPORTE')
    state, _, _ = advance(state, 'CANCELAR')
    assert state['reviews'] == [{'note': 'Revisado manualmente'}]


def test_webhook_verifies_handshake_and_rejects_forged_request(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    monkeypatch.setenv('ISP_SUPPORT_CONNECTION_ID', 'channel1')
    monkeypatch.setenv('META_WEBHOOK_VERIFY_TOKEN', 'test-verify-token')
    monkeypatch.setenv('META_APP_SECRET', 'test-app-secret')
    app = FastAPI()
    app.include_router(support.router)
    app.dependency_overrides[support.get_db] = lambda: None
    client = TestClient(app)
    url = '/v1/isp-support/webhook'
    response = client.get(url, params={'hub.mode': 'subscribe', 'hub.verify_token': 'test-verify-token', 'hub.challenge': '123'})
    assert response.status_code == 200 and response.text == '123'
    assert client.get(url, params={'hub.mode': 'subscribe', 'hub.verify_token': 'wrong'}).status_code == 403
    assert client.post(url, json={}, headers={'x-hub-signature-256': 'sha256=wrong'}).status_code == 403


def configured_channel(db, monkeypatch):
    from cryptography.fernet import Fernet
    from backend.models import ChannelConnection
    ChannelConnection.__table__.create(db.get_bind(), checkfirst=True)
    key = Fernet.generate_key()
    monkeypatch.setenv('APP_ENCRYPTION_KEY', key.decode())
    monkeypatch.setenv('ISP_SUPPORT_CONNECTION_ID', 'channel1')
    monkeypatch.setenv('META_APP_SECRET', 'test-secret')
    monkeypatch.setenv('META_WEBHOOK_VERIFY_TOKEN', 'test-verify')
    monkeypatch.setenv('META_GRAPH_API_VERSION', 'v99.0')  # Solo validación sintáctica.
    monkeypatch.setenv('MIKROWISP_BASE_URL', 'https://isp.example/api/v1')
    monkeypatch.setenv('MIKROWISP_API_TOKEN', 'test-mikrowisp-token')
    monkeypatch.setenv('MIKROWISP_SUPPORT_DEPARTMENT', '1')
    row = ChannelConnection(id_connection='channel1', id_tenant=4, provider='whatsapp',
        account_name='Prueba', phone_number_id='12345',
        credential_encrypted=Fernet(key).encrypt(b'test-meta-token').decode())
    db.add(row)
    db.commit()
    return row


def test_configuration_reports_ready_without_revealing_secrets(db, monkeypatch):
    configured_channel(db, monkeypatch)
    result = support.configuration({'rol': 'admin', 'id_tenant': 4}, db)
    assert result['configured']
    assert result['external_connectivity'] == 'not_tested'
    assert all(isinstance(value, bool) for value in result['checks'].values())
    assert 'test-meta-token' not in str(result)
    assert 'test-mikrowisp-token' not in str(result)


def test_configuration_reports_missing_tables_and_invalid_settings(db, monkeypatch):
    configured_channel(db, monkeypatch)
    ISPSupportEvent.__table__.drop(db.get_bind())
    monkeypatch.setenv('META_GRAPH_API_VERSION', '')
    monkeypatch.setenv('MIKROWISP_SUPPORT_DEPARTMENT', '-1')
    result = support.configuration({'rol': 'admin', 'id_tenant': 4}, db)
    assert not result['configured']
    for name in ['support_tables', 'meta_graph_version', 'support_department']:
        assert not result['checks'][name]


def test_configuration_permissions_and_tenant_isolation(db, monkeypatch):
    configured_channel(db, monkeypatch)
    for user, status in [({'rol': 'cliente', 'id_tenant': 4}, 403),
                         ({'rol': 'admin', 'id_tenant': 5}, 404)]:
        with pytest.raises(HTTPException) as error:
            support.configuration(user, db)
        assert error.value.status_code == status


def test_configuration_can_be_checked_before_activation(db, monkeypatch):
    monkeypatch.delenv('ISP_SUPPORT_CONNECTION_ID', raising=False)
    result = support.configuration({'rol': 'admin', 'id_tenant': 4}, db)
    assert not result['configured']
    assert not result['checks']['connection_selected']


def test_whatsapp_requires_valid_ciphertext_and_matching_key(db, monkeypatch):
    from cryptography.fernet import Fernet
    row = configured_channel(db, monkeypatch)
    assert support.whatsapp_token(row) == 'test-meta-token'
    monkeypatch.setenv('APP_ENCRYPTION_KEY', Fernet.generate_key().decode())
    with pytest.raises(HTTPException):
        support.whatsapp_token(row)
    row.credential_encrypted = 'legacy-plaintext-token'
    with pytest.raises(HTTPException):
        support.whatsapp_token(row)
    monkeypatch.setenv('APP_ENCRYPTION_KEY', 'invalid-key')
    with pytest.raises(HTTPException):
        support.whatsapp_token(row)


def test_mikrowisp_configuration_rejects_unsafe_or_incorrect_url(monkeypatch):
    monkeypatch.setenv('MIKROWISP_API_TOKEN', 'token')
    for url in ['http://isp.example/api/v1', 'https://isp.example',
                'https://user:pass@isp.example/api/v1',
                'https://isp.example/api/v1?token=x', 'https://isp.example/api/v1#fragment']:
        monkeypatch.setenv('MIKROWISP_BASE_URL', url)
        assert not support.mikrowisp_configured()
    monkeypatch.setenv('MIKROWISP_BASE_URL', 'https://isp.example/api/v1/')
    assert support.mikrowisp_configured()


def test_bad_whatsapp_credentials_preserve_created_ticket(db, monkeypatch):
    row = configured_channel(db, monkeypatch)
    row.credential_encrypted = 'legacy-plaintext-token'
    seed(db)
    api = AsyncMock(return_value={'estado': 'exito', 'idticket': '100'})
    monkeypatch.setattr(support, 'mikrowisp', api)
    asyncio.run(support.process_message(db, row, message()))
    assert db.query(ISPSupportEvent).one().status == 'delivery_unknown'
    assert db.query(ISPSupportSession).one().state['ticket_id'] == '100'
    asyncio.run(support.process_message(db, row, message()))
    assert api.await_count == 1
