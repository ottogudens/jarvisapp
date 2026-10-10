"""
J.A.R.V.I.S. SaaS — Modelos ORM (SQLAlchemy / PostgreSQL)

Correcciones aplicadas respecto al blueprint original:
- Fix #1-2: Relaciones bidireccionales con relationship()
- Fix #3:   id_tenant en todas las tablas de dominio (multi-tenancy real)
- Fix #4:   Estado default 'Recepción' (era 'Diagnocompra')
- Fix #5:   Timestamps created_at / updated_at en todas las tablas
"""

import uuid
from sqlalchemy import (
    Column, Integer, BigInteger, String, ForeignKey, DateTime, Text, Boolean, func, JSON, UniqueConstraint
)
from pgvector.sqlalchemy import Vector
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

# Roles disponibles en el sistema
ROL_SUPERADMIN = "superadmin"
ROL_ADMIN = "admin"
ROL_CLIENTE = "cliente"
ROLS_STAFF = (ROL_SUPERADMIN, ROL_ADMIN)  # Acceso total al panel admin


# ============================================================
# SaaS Core: Planes y Tenants
# ============================================================

class SaaSPlan(Base):
    __tablename__ = 'saas_planes'

    id_plan = Column(Integer, primary_key=True, autoincrement=True)
    nombre_plan = Column(String(50), unique=True, nullable=False)
    permite_iot = Column(Boolean, default=False)
    permite_mikrotik = Column(Boolean, default=False)
    permite_telegram = Column(Boolean, default=False)
    permite_whatsapp = Column(Boolean, default=False)
    tokens_mensuales = Column(Integer, default=100000, nullable=False)
    max_documentos = Column(Integer, default=100, nullable=False)
    almacenamiento_bytes = Column(BigInteger, default=1073741824, nullable=False)
    max_upload_bytes = Column(BigInteger, default=15728640, nullable=False)
    precio_mensual = Column(Integer, default=0, nullable=False)  # moneda menor, p. ej. CLP
    moneda = Column(String(3), default="CLP", nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    tenants = relationship("Tenant", back_populates="plan")

    def __repr__(self):
        return f"<SaaSPlan {self.nombre_plan}>"


class Tenant(Base):
    __tablename__ = 'saas_tenants'

    id_tenant = Column(Integer, primary_key=True, autoincrement=True)
    nombre_organizacion = Column(String(150), nullable=False)
    nombre_contacto = Column(String(150), nullable=True)
    telefono = Column(String(50), nullable=True)
    id_plan = Column(Integer, ForeignKey('saas_planes.id_plan'), nullable=False)
    ai_provider = Column(String(50), default="gemini", nullable=False)
    ai_model = Column(String(50), default="gemini-1.5-flash", nullable=False)
    telegram_bot_token = Column(String(200), unique=True, nullable=True)
    telegram_webhook_secret = Column(String(128), nullable=True)
    is_trial = Column(Boolean, default=False, nullable=False)
    trial_ends_at = Column(DateTime(timezone=True), nullable=True)
    trial_daily_token_limit = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    suspended_at = Column(DateTime(timezone=True), nullable=True)
    suspension_reason = Column(String(255), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships (Fix #1)
    plan = relationship("SaaSPlan", back_populates="tenants")
    usuarios = relationship("Usuario", back_populates="tenant", cascade="all, delete-orphan")
    clientes = relationship("Cliente", back_populates="tenant", cascade="all, delete-orphan")
    perfiles_asignados = relationship("TenantProfile", back_populates="tenant", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Tenant {self.nombre_organizacion}>"

class SystemSettings(Base):
    __tablename__ = 'system_settings'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(String(500), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

class AIUsageStats(Base):
    __tablename__ = 'ai_usage_stats'
    
    id_stat = Column(Integer, primary_key=True, autoincrement=True)
    id_tenant = Column(Integer, ForeignKey('saas_tenants.id_tenant'), nullable=False)
    proveedor = Column(String(50), nullable=False)
    tokens_consumidos = Column(Integer, default=0)
    solicitudes_realizadas = Column(Integer, default=0)
    fecha_registro = Column(DateTime, server_default=func.now(), nullable=False)



# ============================================================
# Perfiles Dinámicos de IA
# ============================================================

class JarvisProfile(Base):
    __tablename__ = 'jarvis_profiles'

    id_perfil = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(100), unique=True, nullable=False)
    instrucciones_base = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<JarvisProfile {self.nombre}>"

class TenantProfile(Base):
    __tablename__ = 'tenant_profiles'

    id_tenant_profile = Column(Integer, primary_key=True, autoincrement=True)
    id_tenant = Column(Integer, ForeignKey('saas_tenants.id_tenant', ondelete='CASCADE'), nullable=False)
    id_perfil = Column(Integer, ForeignKey('jarvis_profiles.id_perfil', ondelete='CASCADE'), nullable=False)
    instrucciones_extra = Column(Text, default="", nullable=True)

    # Relaciones
    tenant = relationship("Tenant", back_populates="perfiles_asignados")
    perfil = relationship("JarvisProfile")


class CustomAssistantProfile(Base):
    """Perfil creado por un cliente y aislado de los perfiles globales."""
    __tablename__ = 'custom_assistant_profiles'

    id_profile = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    id_tenant = Column(Integer, ForeignKey('saas_tenants.id_tenant', ondelete='CASCADE'), index=True, nullable=False)
    id_usuario = Column(Integer, ForeignKey('usuarios.id_usuario', ondelete='SET NULL'), nullable=True)
    nombre = Column(String(100), nullable=False)
    personalidad = Column(String(255), nullable=False, default='Profesional, cercano y claro')
    requisitos = Column(JSON, nullable=False, default=dict)
    master_prompt = Column(Text, nullable=False, default='')
    knowledge_document_ids = Column(JSON, nullable=False, default=list)
    source_urls = Column(JSON, nullable=False, default=list)
    estado = Column(String(20), nullable=False, default='draft')
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class BillingSubscription(Base):
    __tablename__ = 'billing_subscriptions'
    id_subscription = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    id_tenant = Column(Integer, ForeignKey('saas_tenants.id_tenant', ondelete='CASCADE'), index=True, nullable=False)
    id_plan = Column(Integer, ForeignKey('saas_planes.id_plan'), nullable=False)
    provider = Column(String(30), nullable=False, default='mercadopago')
    provider_subscription_id = Column(String(120), unique=True, nullable=True)
    status = Column(String(30), nullable=False, default='pending')
    amount = Column(Integer, nullable=False, default=0)
    currency = Column(String(3), nullable=False, default='CLP')
    checkout_url = Column(Text, nullable=True)
    raw_status = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ChannelConnection(Base):
    __tablename__ = 'channel_connections'
    id_connection = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    id_tenant = Column(Integer, ForeignKey('saas_tenants.id_tenant', ondelete='CASCADE'), index=True, nullable=False)
    provider = Column(String(30), nullable=False)  # whatsapp, instagram, messenger, facebook_ads
    account_name = Column(String(255), nullable=False)
    external_account_id = Column(String(255), nullable=True)
    phone_number_id = Column(String(255), nullable=True)
    credential_encrypted = Column(Text, nullable=True)
    scopes = Column(JSON, nullable=False, default=list)
    status = Column(String(30), nullable=False, default='draft')
    metadata_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class OmniConversation(Base):
    __tablename__ = 'omni_conversations'
    id_conversation = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    id_tenant = Column(Integer, ForeignKey('saas_tenants.id_tenant', ondelete='CASCADE'), index=True, nullable=False)
    id_connection = Column(String(36), ForeignKey('channel_connections.id_connection', ondelete='CASCADE'), nullable=False)
    external_conversation_id = Column(String(255), nullable=True)
    customer_name = Column(String(255), nullable=True)
    customer_external_id = Column(String(255), nullable=True)
    status = Column(String(30), nullable=False, default='open')
    assigned_to = Column(Integer, ForeignKey('usuarios.id_usuario', ondelete='SET NULL'), nullable=True)
    last_message_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class OmniMessage(Base):
    __tablename__ = 'omni_messages'
    id_message = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    id_conversation = Column(String(36), ForeignKey('omni_conversations.id_conversation', ondelete='CASCADE'), index=True, nullable=False)
    direction = Column(String(12), nullable=False)  # inbound/outbound
    content = Column(Text, nullable=False)
    external_message_id = Column(String(255), nullable=True)
    ai_generated = Column(Boolean, default=False, nullable=False)
    status = Column(String(30), default='received', nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class MarketingContent(Base):
    __tablename__ = 'marketing_content'
    id_content = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    id_tenant = Column(Integer, ForeignKey('saas_tenants.id_tenant', ondelete='CASCADE'), index=True, nullable=False)
    id_connection = Column(String(36), ForeignKey('channel_connections.id_connection', ondelete='SET NULL'), nullable=True)
    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)
    status = Column(String(30), nullable=False, default='draft')
    scheduled_at = Column(DateTime(timezone=True), nullable=True)
    approved_by = Column(Integer, ForeignKey('usuarios.id_usuario', ondelete='SET NULL'), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# ============================================================
# Usuarios
# ============================================================

class Usuario(Base):
    __tablename__ = 'usuarios'

    id_usuario = Column(Integer, primary_key=True, autoincrement=True)
    id_tenant = Column(Integer, ForeignKey('saas_tenants.id_tenant', ondelete='CASCADE'), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    # Aumenta al cerrar sesión, cambiar contraseña o alterar privilegios. Los
    # JWT previos quedan invalidados sin necesitar una lista de bloqueados.
    session_version = Column(Integer, nullable=False, default=0)
    perfil_jarvis = Column(String(50), nullable=True)  # Deprecado
    active_profile_ids = Column(JSON, default=list)
    active_custom_profile_id = Column(String(36), ForeignKey('custom_assistant_profiles.id_profile', ondelete='SET NULL'), nullable=True)
    rol = Column(String(20), nullable=False, default=ROL_CLIENTE)  # 'superadmin', 'admin', 'cliente'
    is_superadmin = Column(Boolean, default=False, nullable=False)  # Alias de compatibilidad: rol == 'superadmin'
    tokens_consumidos = Column(Integer, default=0, nullable=False)
    telegram_chat_id = Column(BigInteger, nullable=True, index=True)
    telegram_username = Column(String(100), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships (Fix #2)
    tenant = relationship("Tenant", back_populates="usuarios")
    chat_sessions = relationship("ChatSession", back_populates="usuario", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Usuario {self.email} [{self.perfil_jarvis}]>"


# ============================================================
# Dominio de Negocio: Clientes, Vehículos, Órdenes, Pagos
# Todas las tablas incluyen id_tenant para aislamiento multi-tenant (Fix #3)
# ============================================================

class Cliente(Base):
    __tablename__ = 'clientes'

    id_cliente = Column(Integer, primary_key=True, autoincrement=True)
    id_tenant = Column(Integer, ForeignKey('saas_tenants.id_tenant', ondelete='CASCADE'), nullable=False)
    rut = Column(String(12), unique=True, nullable=False)
    nombre = Column(String(150), nullable=False)
    telefono = Column(String(20))
    email = Column(String(100))
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    tenant = relationship("Tenant", back_populates="clientes")
    vehiculos = relationship("Vehiculo", back_populates="cliente", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Cliente {self.rut} — {self.nombre}>"


class Vehiculo(Base):
    __tablename__ = 'vehiculos'

    id_vehiculo = Column(Integer, primary_key=True, autoincrement=True)
    id_tenant = Column(Integer, ForeignKey('saas_tenants.id_tenant', ondelete='CASCADE'), nullable=False)
    patente = Column(String(8), unique=True, nullable=False)
    marca = Column(String(50), nullable=False)
    modelo = Column(String(50), nullable=False)
    id_cliente = Column(Integer, ForeignKey('clientes.id_cliente'))
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    tenant = relationship("Tenant")
    cliente = relationship("Cliente", back_populates="vehiculos")
    ordenes = relationship("OrdenTrabajo", back_populates="vehiculo", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Vehiculo {self.patente} — {self.marca} {self.modelo}>"


class OrdenTrabajo(Base):
    __tablename__ = 'ordenes_trabajo'

    id_orden = Column(Integer, primary_key=True, autoincrement=True)
    id_tenant = Column(Integer, ForeignKey('saas_tenants.id_tenant', ondelete='CASCADE'), nullable=False)
    folio_ot = Column(String(20), unique=True, nullable=False)
    id_vehiculo = Column(Integer, ForeignKey('vehiculos.id_vehiculo'), nullable=False)
    estado = Column(String(30), default='Recepción')  # Fix #4: era 'Diagnocompra'
    diagnostico_ia = Column(Text)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    tenant = relationship("Tenant")
    vehiculo = relationship("Vehiculo", back_populates="ordenes")
    pagos = relationship("PagoMercadoPago", back_populates="orden", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<OrdenTrabajo {self.folio_ot} [{self.estado}]>"


class PagoMercadoPago(Base):
    __tablename__ = 'pagos_mercado_pago'

    id_pago = Column(Integer, primary_key=True, autoincrement=True)
    id_tenant = Column(Integer, ForeignKey('saas_tenants.id_tenant', ondelete='CASCADE'), nullable=False)
    id_orden = Column(Integer, ForeignKey('ordenes_trabajo.id_orden'), nullable=False)
    id_transaccion_mp = Column(String(100), unique=True, nullable=False)
    monto_pagado = Column(Integer, nullable=False)
    estado_pago = Column(String(30), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    tenant = relationship("Tenant")
    orden = relationship("OrdenTrabajo", back_populates="pagos")

    def __repr__(self):
        return f"<PagoMercadoPago {self.id_transaccion_mp} ${self.monto_pagado}>"

# ============================================================
# Chat Persistente (J.A.R.V.I.S. Multimodal)
# ============================================================

class ChatSession(Base):
    __tablename__ = 'chat_sessions'
    
    id_session = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    id_usuario = Column(Integer, ForeignKey('usuarios.id_usuario', ondelete='CASCADE'), nullable=False)
    titulo = Column(String(150), nullable=True)
    active_knowledge_folder_id = Column(String(36), ForeignKey('knowledge_folders.id_folder', ondelete='SET NULL'), nullable=True, index=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    usuario = relationship("Usuario", back_populates="chat_sessions")
    mensajes = relationship("ChatMessage", back_populates="sesion", cascade="all, delete-orphan", order_by="ChatMessage.created_at")


class ChatMessage(Base):
    __tablename__ = 'chat_messages'
    
    id_mensaje = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    id_session = Column(String(36), ForeignKey('chat_sessions.id_session', ondelete='CASCADE'), nullable=False)
    rol = Column(String(20), nullable=False) # 'user' o 'jarvis'
    contenido = Column(Text, nullable=False)
    file_urls = Column(JSON, nullable=True, default=list) # Lista de URLs de Supabase Storage
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    
    # Relationships
    sesion = relationship("ChatSession", back_populates="mensajes")

# ============================================================
# Configuracion IoT (Home Assistant & MQTT)
# ============================================================

class IoTConfig(Base):
    __tablename__ = 'iot_configs'

    id_iot_config = Column(Integer, primary_key=True, autoincrement=True)
    id_usuario = Column(Integer, ForeignKey('usuarios.id_usuario', ondelete='CASCADE'), unique=True, nullable=False)
    
    # Home Assistant
    ha_url = Column(String(255), nullable=True)
    ha_token = Column(Text, nullable=True)
    
    # MQTT
    mqtt_broker = Column(String(255), nullable=True)
    mqtt_port = Column(Integer, default=1883)
    mqtt_user = Column(String(100), nullable=True)
    mqtt_password = Column(String(255), nullable=True)
    mqtt_auto_connect = Column(Boolean, default=False)
    
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    usuario = relationship("Usuario")

    def __repr__(self):
        return f"<IoTConfig Usuario:{self.id_usuario}>"

class KnowledgeFolder(Base):
    __tablename__ = 'knowledge_folders'

    id_folder = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    id_tenant = Column(Integer, ForeignKey('saas_tenants.id_tenant', ondelete='CASCADE'), index=True, nullable=False)
    parent_id = Column(String(36), ForeignKey('knowledge_folders.id_folder', ondelete='SET NULL'), nullable=True, index=True)
    nombre = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    tenant = relationship("Tenant")
    documentos = relationship("KnowledgeDocument", back_populates="folder")
    parent = relationship("KnowledgeFolder", remote_side=[id_folder], backref="subcarpetas")


class KnowledgeDocument(Base):
    __tablename__ = 'knowledge_documents'

    id_document = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    id_tenant = Column(Integer, ForeignKey('saas_tenants.id_tenant', ondelete='CASCADE'), index=True, nullable=False)
    id_usuario = Column(Integer, ForeignKey('usuarios.id_usuario', ondelete='SET NULL'), nullable=True)
    id_folder = Column(String(36), ForeignKey('knowledge_folders.id_folder', ondelete='SET NULL'), nullable=True)
    nombre = Column(String(255), nullable=False)
    # El binario vive en Storage privado; aquí queda la identidad, procedencia
    # y estado que comparten todos los canales (web, Telegram, etc.).
    storage_path = Column(Text, nullable=True)
    mime_type = Column(String(120), nullable=True)
    byte_size = Column(BigInteger, nullable=False, default=0)
    content_sha256 = Column(String(64), nullable=True, index=True)
    source_channel = Column(String(30), nullable=False, default="web")
    version = Column(Integer, nullable=False, default=1)
    replaces_document_id = Column(String(36), ForeignKey('knowledge_documents.id_document', ondelete='SET NULL'), nullable=True)
    status = Column(String(20), nullable=False, default="processing")
    error_message = Column(Text, nullable=True)
    chunk_count = Column(Integer, nullable=False, default=0)
    indexed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    tenant = relationship("Tenant")
    usuario = relationship("Usuario")
    folder = relationship("KnowledgeFolder", back_populates="documentos")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")

class DocumentChunk(Base):
    __tablename__ = 'document_chunks'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    id_document = Column(String(36), ForeignKey('knowledge_documents.id_document', ondelete='CASCADE'), index=True, nullable=True)
    id_mensaje = Column(String(36), ForeignKey('chat_messages.id_mensaje', ondelete='CASCADE'), index=True, nullable=True)
    chunk_index = Column(Integer)
    texto = Column(Text)
    embedding = Column(Vector(768))
    metadata_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    document = relationship("KnowledgeDocument", back_populates="chunks")


class KnowledgeIngestionJob(Base):
    """Trabajo durable para extraer e indexar documentos fuera de la petición HTTP."""
    __tablename__ = 'knowledge_ingestion_jobs'

    id_job = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    id_document = Column(String(36), ForeignKey('knowledge_documents.id_document', ondelete='CASCADE'), unique=True, nullable=False)
    status = Column(String(20), nullable=False, default='queued', index=True)
    attempts = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=3)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    # Campos visibles para que la biblioteca pueda informar progreso real, no
    # una estimación únicamente basada en el estado de la cola.
    stage = Column(String(40), nullable=False, default="queued")
    progress_percent = Column(Integer, nullable=False, default=0)
    total_chunks = Column(Integer, nullable=False, default=0)
    processed_chunks = Column(Integer, nullable=False, default=0)

    document = relationship("KnowledgeDocument")


class KnowledgeRetrievalAudit(Base):
    """Auditoría minimizada de recuperación RAG, sin almacenar el texto de la consulta."""
    __tablename__ = 'knowledge_retrieval_audit'

    id_audit = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    id_tenant = Column(Integer, ForeignKey('saas_tenants.id_tenant', ondelete='CASCADE'), index=True, nullable=False)
    id_usuario = Column(Integer, ForeignKey('usuarios.id_usuario', ondelete='SET NULL'), nullable=True)
    channel = Column(String(30), nullable=False, default='web')
    query_sha256 = Column(String(64), nullable=False)
    result_document_ids = Column(JSON, nullable=False, default=list)
    result_chunk_ids = Column(JSON, nullable=False, default=list)
    result_scores = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class TelegramWebhookEvent(Base):
    """Registro idempotente de entregas de Telegram por organización."""
    __tablename__ = 'telegram_webhook_events'
    __table_args__ = (UniqueConstraint('id_tenant', 'update_id', name='uq_telegram_event_tenant_update'),)

    id_event = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    id_tenant = Column(Integer, ForeignKey('saas_tenants.id_tenant', ondelete='CASCADE'), index=True, nullable=False)
    update_id = Column(BigInteger, nullable=False)
    status = Column(String(20), nullable=False, default='processing', index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    processed_at = Column(DateTime(timezone=True), nullable=True)


class DocumentTemplate(Base):
    """Plantillas del tenant. El original se conserva inmutable en base64."""
    __tablename__ = 'document_templates'

    id_template = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    id_tenant = Column(Integer, ForeignKey('saas_tenants.id_tenant', ondelete='CASCADE'), index=True, nullable=False)
    id_usuario = Column(Integer, ForeignKey('usuarios.id_usuario', ondelete='SET NULL'), nullable=True)
    nombre = Column(String(255), nullable=False)
    extension = Column(String(12), nullable=False)
    contenido_base64 = Column(Text, nullable=False)
    campos = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class MikrotikRouter(Base):
    __tablename__ = 'mikrotik_routers'

    id_router = Column(Integer, primary_key=True, autoincrement=True)
    id_tenant = Column(Integer, ForeignKey('saas_tenants.id_tenant', ondelete='CASCADE'), nullable=False)
    nombre = Column(String(100), nullable=False)
    ip_address = Column(String(50), nullable=False)
    api_port = Column(Integer, default=443)
    username = Column(String(100), nullable=False)
    password = Column(String(255), nullable=False)
    is_connected = Column(Boolean, default=False)
    last_error = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class MQTTSubscription(Base):
    __tablename__ = 'mqtt_subscriptions'

    id_subscription = Column(Integer, primary_key=True, autoincrement=True)
    id_usuario = Column(Integer, ForeignKey('usuarios.id_usuario', ondelete='CASCADE'), index=True, nullable=False)
    topic = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class MQTTMessageCache(Base):
    __tablename__ = 'mqtt_message_cache'

    id_message = Column(Integer, primary_key=True, autoincrement=True)
    id_usuario = Column(Integer, ForeignKey('usuarios.id_usuario', ondelete='CASCADE'), index=True, nullable=False)
    topic = Column(String(255), index=True, nullable=False)
    payload = Column(Text, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
