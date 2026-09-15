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
    Column, Integer, String, ForeignKey, DateTime, Text, Boolean, func, JSON
)
from pgvector.sqlalchemy import Vector
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


# ============================================================
# SaaS Core: Planes y Tenants
# ============================================================

class SaaSPlan(Base):
    __tablename__ = 'saas_planes'

    id_plan = Column(Integer, primary_key=True, autoincrement=True)
    nombre_plan = Column(String(50), unique=True, nullable=False)
    permite_erp = Column(Boolean, default=False)
    permite_inspeccion = Column(Boolean, default=False)
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
    id_plan = Column(Integer, ForeignKey('saas_planes.id_plan'), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships (Fix #1)
    plan = relationship("SaaSPlan", back_populates="tenants")
    usuarios = relationship("Usuario", back_populates="tenant", cascade="all, delete-orphan")
    clientes = relationship("Cliente", back_populates="tenant", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Tenant {self.nombre_organizacion}>"


# ============================================================
# Usuarios
# ============================================================

class Usuario(Base):
    __tablename__ = 'usuarios'

    id_usuario = Column(Integer, primary_key=True, autoincrement=True)
    id_tenant = Column(Integer, ForeignKey('saas_tenants.id_tenant', ondelete='CASCADE'), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    perfil_jarvis = Column(String(50), nullable=False)  # 'Mecanico', 'Inspector_DGC', 'Enfermera_Paliativos'
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
    
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    usuario = relationship("Usuario")

    def __repr__(self):
        return f"<IoTConfig Usuario:{self.id_usuario}>"

class DocumentChunk(Base):
    __tablename__ = 'document_chunks'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    id_mensaje = Column(String(36), ForeignKey('chat_messages.id_mensaje', ondelete='CASCADE'), index=True)
    chunk_index = Column(Integer)
    texto = Column(Text)
    embedding = Column(Vector(768))
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
    created_at = Column(DateTime(timezone=True), server_default=func.now())
