"""
J.A.R.V.I.S. Core Engine — Servidor FastAPI

Correcciones aplicadas:
- Fix #10: Autenticación obligatoria en todos los endpoints de negocio
- Fix #11: Lifespan context manager en vez de @app.on_event("startup")
- Fix #12: tempfile.NamedTemporaryFile para cleanup seguro de archivos
- Fix #13: Respuesta JSON con audio en base64 (no headers con encoding roto)
- Fix #14: Consulta y actualización real de OrdenTrabajo en BD
- Fix #15: Verificación de firma en webhook de MercadoPago
- Fix #16: CORS middleware configurado
- Fix #17: Endpoints para Inspector DGC y Enfermera Paliativos
"""

import os
import base64
import json
import tempfile
import hashlib
import hmac
from typing import Type, List, Optional
from contextlib import asynccontextmanager

from fastapi import (
    FastAPI, UploadFile, File, Form, Depends, HTTPException, Request, Response, Header,
)
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google import genai
from google.genai import types
from elevenlabs.client import ElevenLabs as ElevenLabsClient
from elevenlabs import VoiceSettings
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.database import get_db, inicializar_base_de_datos_remota
from backend.auth import router as auth_router, obtener_usuario_actual, requiere_feature
from backend.mikrotik import router as mikrotik_router
from backend.admin import router as admin_router
from backend.models import OrdenTrabajo, ChatSession, ChatMessage, DocumentChunk, Usuario
from supabase import create_client, Client


# ============================================================
# Lifespan (Fix #11: reemplaza @app.on_event("startup"))
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa la BD al arrancar y limpia recursos al cerrar."""
    inicializar_base_de_datos_remota()
    yield


# ============================================================
# Instancia de FastAPI
# ============================================================

app = FastAPI(
    title="J.A.R.V.I.S. Core Engine",
    description="Sistema Multi-Tenant SaaS de asistentes virtuales de voz especializados por industria.",
    version="1.0.0",
    lifespan=lifespan,
)

# Fix #16: CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Fix #7: incluir router de autenticación
app.include_router(auth_router)
app.include_router(mikrotik_router)
app.include_router(admin_router)


# Inicialización lazy: se crean al primer uso para evitar errores si
# las API keys no están configuradas (ej: durante tests o imports).
_client_gemini = None
_client_elevenlabs = None


def get_gemini_client() -> genai.Client:
    global _client_gemini
    if _client_gemini is None:
        _client_gemini = genai.Client(api_key=os.getenv("GEMINI_API_KEY", ""))
    return _client_gemini


def get_elevenlabs_client() -> ElevenLabsClient:
    global _client_elevenlabs
    if _client_elevenlabs is None:
        _client_elevenlabs = ElevenLabsClient(api_key=os.getenv("ELEVENLABS_API_KEY", ""))
    return _client_elevenlabs


# ============================================================
# System Prompts por perfil de usuario
# ============================================================

SYSTEM_PROMPTS = {
    "Mecanico": (
        "Eres J.A.R.V.I.S., asistente virtual. "
        "Tienes una personalidad relajada, amigable y masculina, con un toque latino, pero mantienes una notable cuota de sarcasmo e ironía sutil cuando es oportuno. Dirígete al usuario de forma respetuosa pero cercana. "
        "Tu especialidad incluye integraciones IoT y asistencia general.\n"
        "Responde de forma MUY concisa y directa, sin rodeos. Sé conversacional, amigable y fluido, ideal para voz hablada."
    ),
    "Inspector_DGC": (
        "Eres J.A.R.V.I.S., asistente virtual de inspección fiscal para la Dirección General de Consumo. "
        "Eres británico, educado, implacable y sutilmente irónico. Dirígete al usuario como 'Señor Inspector'. "
        "Tu especialidad incluye:\n"
        "- Verificación de cumplimiento normativo en establecimientos comerciales\n"
        "- Redacción de actas de inspección y observaciones\n"
        "- Consulta de regulaciones vigentes\n"
        "- Seguimiento de procesos sancionatorios\n"
        "Responde de forma MUY concisa, directa y con rigor legal. Usa ironía cuando menciones faltas graves o excusas de los infractores."
    ),
    "Enfermera_Paliativos": (
        "Eres J.A.R.V.I.S., asistente virtual de enfermería en cuidados paliativos. "
        "Eres británico, educado, empático pero con un sutil sentido del humor irónico para aliviar tensiones. Dirígete al usuario según su género. "
        "Tu especialidad incluye:\n"
        "- Registro de signos vitales y síntomas del paciente\n"
        "- Protocolos de manejo del dolor (escala EVA/NRS)\n"
        "- Coordinación de cuidados y medicación\n"
        "- Soporte emocional y comunicación con familias\n"
        "Responde de forma MUY concisa y cálida, usando ironía muy ligera solo si el contexto lo permite sin faltar el respeto."
    ),
}


# ============================================================
# Schema de respuesta (Fix #13: JSON en vez de headers)
# ============================================================

class JarvisResponse(BaseModel):
    """Respuesta unificada del pipeline de IA."""
    transcripcion: str
    respuesta_texto: str
    diagnostico_ia: str | None = None
    audio_base64: str


class RespuestaMecanico(BaseModel):
    """Esquema de extracción estructurada para el perfil Mecánico."""
    transcripcion_usuario: str
    diagnostico_tecnico: str
    repuestos_requeridos: list[str]
    estado_sugerido: str
    mensaje_para_usuario: str


class RespuestaInspector(BaseModel):
    """Esquema de extracción estructurada para el perfil Inspector DGC."""
    transcripcion_usuario: str
    tipo_infraccion: str
    descripcion_hallazgo: str
    normativa_aplicable: str
    gravedad: str  # Leve, Grave, Gravísima
    accion_recomendada: str
    mensaje_para_usuario: str


# ============================================================
# Pipeline central de IA: STT → GPT-4 → TTS
# ============================================================

async def _pipeline_ia(
    audio_file: UploadFile,
    perfil: str,
    contexto_extra: str = "",
    response_format: Type[BaseModel] | None = None,
) -> tuple[JarvisResponse, BaseModel | None]:
    """
    Pipeline reutilizable por todos los perfiles:
    1. Whisper (STT) → transcribe audio a texto
    2. GPT-4         → clasifica intención y genera respuesta
    3. ElevenLabs    → sintetiza respuesta a voz

    Fix #12: usa tempfile para cleanup seguro.
    Fix #13: retorna JSON con audio en base64.
    """
    # 1. Leer audio directamente en memoria
    audio_bytes = await audio_file.read()

    try:
        system_prompt = SYSTEM_PROMPTS.get(perfil, SYSTEM_PROMPTS["Mecanico"])
        if contexto_extra:
            system_prompt += f"\n\nContexto operativo actual:\n{contexto_extra}"

        # 2. Generación multimodal con Gemini 1.5 Flash
        client = get_gemini_client()
        
        mime_type = audio_file.content_type if audio_file.content_type else "audio/mp4"
        audio_part = types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)
        
        prompt_text = (
            "Transcribe el audio adjunto e incluye la transcripcion exacta en el campo 'transcripcion_usuario' de la respuesta JSON. "
            "Responde a la solicitud de acuerdo a tus instrucciones."
        )

        config_args = {
            "system_instruction": system_prompt,
            "response_mime_type": "application/json",
            "temperature": 0.7,
        }
        
        if response_format:
            config_args["response_schema"] = response_format

        respuesta_gemini = client.models.generate_content(
            model='gemini-3.6-flash',
            contents=[audio_part, prompt_text],
            config=types.GenerateContentConfig(**config_args),
        )

        if response_format:
            parsed_data = response_format.model_validate_json(respuesta_gemini.text)
            respuesta_texto = getattr(parsed_data, "mensaje_para_usuario", "")
            texto_usuario = getattr(parsed_data, "transcripcion_usuario", "")
        else:
            data = json.loads(respuesta_gemini.text)
            respuesta_texto = data.get("mensaje_para_usuario", "")
            texto_usuario = data.get("transcripcion_usuario", "")
            parsed_data = None

        # 3. Text-to-Speech con ElevenLabs (con fallback seguro si la API key o cuota falla)
        audio_b64 = ""
        try:
            voice_id = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
            audio_response = get_elevenlabs_client().generate(
                text=respuesta_texto,
                voice=voice_id,
                model="eleven_multilingual_v2",
                voice_settings=VoiceSettings(stability=0.30, similarity_boost=0.75, style=0.0, use_speaker_boost=True)
            )
            audio_tts = b"".join(audio_response)
            audio_b64 = base64.b64encode(audio_tts).decode("utf-8")
        except Exception as tts_err:
            print(f"⚠️ Error generando audio con ElevenLabs (fallback a solo texto): {tts_err}")

        response_obj = JarvisResponse(
            transcripcion=texto_usuario,
            respuesta_texto=respuesta_texto,
            audio_base64=audio_b64,
        )
        return response_obj, parsed_data

    except Exception as e:
        print(f"Error procesando IA: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# Endpoint: Mecánico — Pipeline completo con ERP
# (Fix #10: con autenticación, Fix #14: consulta BD)
# ============================================================

@app.post("/v1/jarvis/mecanico/procesar-completo", response_model=JarvisResponse)
async def pipeline_mecanico(
    audio_file: UploadFile = File(...),
    id_orden: str = Form(...),
    usuario: dict = Depends(requiere_feature("modulo_erp")),
    db: Session = Depends(get_db),
):
    """
    Pipeline para perfil Mecánico:
    - Recibe audio + folio de orden de trabajo
    - Transcribe, genera diagnóstico IA, sintetiza respuesta
    - Actualiza la orden en la base de datos
    """
    # Fix #14: consultar la orden real en BD, filtrada por tenant
    orden = db.query(OrdenTrabajo).filter(
        OrdenTrabajo.folio_ot == id_orden,
        OrdenTrabajo.id_tenant == usuario["id_tenant"],
    ).first()

    contexto = ""
    if orden:
        contexto = (
            f"Orden de trabajo: {orden.folio_ot}\n"
            f"Estado actual: {orden.estado}\n"
            f"Diagnóstico previo: {orden.diagnostico_ia or 'Sin diagnóstico previo'}"
        )

    # Le decimos al prompt que requerirá JSON si es necesario
    contexto += "\n(IMPORTANTE: Extrae repuestos, diagnóstico y estado sugerido. Genera un mensaje amigable para el cliente en 'mensaje_para_usuario')."
    
    respuesta, parsed = await _pipeline_ia(audio_file, "Mecanico", contexto, response_format=RespuestaMecanico)

    # Actualizar base de datos con los datos estructurados extraídos
    if orden and parsed:
        orden.diagnostico_ia = parsed.diagnostico_tecnico
        orden.estado = parsed.estado_sugerido
        
        # Opcional: podríamos guardar los repuestos en un campo JSON o log,
        # por ahora lo sumamos al diagnóstico
        if parsed.repuestos_requeridos:
            orden.diagnostico_ia += "\n\nRepuestos: " + ", ".join(parsed.repuestos_requeridos)
            
        db.commit()
        respuesta.diagnostico_ia = orden.diagnostico_ia

    return respuesta


# ============================================================
# Endpoint: Inspector DGC (Fix #17)
# ============================================================

@app.post("/v1/jarvis/inspector/procesar-completo", response_model=JarvisResponse)
async def pipeline_inspector(
    audio_file: UploadFile = File(...),
    usuario: dict = Depends(requiere_feature("modulo_inspeccion")),
):
    """Pipeline para perfil Inspector Fiscal DGC con extracción estructurada."""
    contexto = (
        "(IMPORTANTE: Extrae tipo de infracción, descripción del hallazgo, normativa aplicable, "
        "gravedad (Leve/Grave/Gravísima) y acción recomendada. Genera un resumen profesional en 'mensaje_para_usuario'.)"
    )
    respuesta, parsed = await _pipeline_ia(audio_file, "Inspector_DGC", contexto, response_format=RespuestaInspector)
    
    if parsed:
        respuesta.diagnostico_ia = (
            f"Tipo: {parsed.tipo_infraccion}\n"
            f"Hallazgo: {parsed.descripcion_hallazgo}\n"
            f"Normativa: {parsed.normativa_aplicable}\n"
            f"Gravedad: {parsed.gravedad}\n"
            f"Acción: {parsed.accion_recomendada}"
        )
    
    return respuesta


# ============================================================
# Endpoint: Enfermera Paliativos (Fix #17)
# ============================================================

@app.post("/v1/jarvis/enfermera/procesar-completo", response_model=JarvisResponse)
async def pipeline_enfermera(
    audio_file: UploadFile = File(...),
    usuario: dict = Depends(requiere_feature("modulo_enfermeria")),
):
    """Pipeline para perfil Enfermera de Cuidados Paliativos."""
    respuesta, _ = await _pipeline_ia(audio_file, "Enfermera_Paliativos")
    return respuesta


# ============================================================
# Webhook MercadoPago (Fix #15: verificación de firma)
# ============================================================

MP_WEBHOOK_SECRET = os.getenv("MP_WEBHOOK_SECRET", "")


@app.post("/v1/mercado-pago/webhook")
async def webhook_mp(request: Request):
    """
    Recibe notificaciones de pago de MercadoPago.
    Fix #15: valida la firma HMAC del webhook cuando MP_WEBHOOK_SECRET está configurado.
    """
    payload_bytes = await request.body()

    if MP_WEBHOOK_SECRET:
        # Extraer componentes de la firma
        x_signature = request.headers.get("x-signature", "")
        x_request_id = request.headers.get("x-request-id", "")

        parts = {}
        for item in x_signature.split(","):
            if "=" in item:
                k, v = item.strip().split("=", 1)
                parts[k] = v

        ts = parts.get("ts", "")
        v1 = parts.get("v1", "")

        # Reconstruir el manifest para verificación
        payload = json.loads(payload_bytes)
        data_id = str(payload.get("data", {}).get("id", ""))
        manifest = f"id:{data_id};request-id:{x_request_id};ts:{ts};"

        expected = hmac.new(
            MP_WEBHOOK_SECRET.encode(), manifest.encode(), hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(v1, expected):
            raise HTTPException(status_code=403, detail="Firma de webhook inválida.")
    else:
        payload = json.loads(payload_bytes)

    # Procesar evento de pago
    action = payload.get("action", "")
    if action == "payment.created":
        payment_id = payload.get("data", {}).get("id", "desconocido")
        print(f"[MercadoPago] Pago creado: {payment_id}")

    return Response(content="OK", status_code=200)


# ============================================================
# Endpoints: Chat Multimodal Persistente con J.A.R.V.I.S.
# ============================================================

class CreateSessionRequest(BaseModel):
    titulo: Optional[str] = "Nueva Conversación"


@app.get("/v1/chat/sessions")
async def listar_sesiones(
    usuario: dict = Depends(obtener_usuario_actual),
    db: Session = Depends(get_db)
):
    sessions = db.query(ChatSession).filter(ChatSession.id_usuario == usuario["id_usuario"]).order_by(ChatSession.updated_at.desc()).all()
    return [
        {
            "id_session": s.id_session,
            "titulo": s.titulo or "Conversación con JARVIS",
            "created_at": s.created_at.isoformat(),
            "updated_at": s.updated_at.isoformat(),
        }
        for s in sessions
    ]


@app.post("/v1/chat/sessions")
async def crear_sesion(
    body: CreateSessionRequest = CreateSessionRequest(),
    usuario: dict = Depends(obtener_usuario_actual),
    db: Session = Depends(get_db)
):
    nueva_sesion = ChatSession(
        id_usuario=usuario["id_usuario"],
        titulo=body.titulo or "Nueva Conversación"
    )
    db.add(nueva_sesion)
    db.commit()
    db.refresh(nueva_sesion)
    return {
        "id_session": nueva_sesion.id_session,
        "titulo": nueva_sesion.titulo,
        "created_at": nueva_sesion.created_at.isoformat(),
        "updated_at": nueva_sesion.updated_at.isoformat(),
    }


@app.patch("/v1/chat/sessions/{session_id}")
async def actualizar_sesion(
    session_id: str,
    body: CreateSessionRequest,
    usuario: dict = Depends(obtener_usuario_actual),
    db: Session = Depends(get_db)
):
    sesion = db.query(ChatSession).filter(
        ChatSession.id_session == session_id,
        ChatSession.id_usuario == usuario["id_usuario"]
    ).first()
    if not sesion:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    
    if body.titulo:
        sesion.titulo = body.titulo
    db.commit()
    db.refresh(sesion)
    return {"message": "Sesión actualizada", "titulo": sesion.titulo}


@app.delete("/v1/chat/sessions/{session_id}")
async def eliminar_sesion(
    session_id: str,
    usuario: dict = Depends(obtener_usuario_actual),
    db: Session = Depends(get_db)
):
    sesion = db.query(ChatSession).filter(
        ChatSession.id_session == session_id,
        ChatSession.id_usuario == usuario["id_usuario"]
    ).first()
    if not sesion:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    
    db.delete(sesion)
    db.commit()
    return {"message": "Sesión eliminada correctamente"}


@app.get("/v1/chat/sessions/all/files")
async def listar_todos_archivos(
    usuario: dict = Depends(obtener_usuario_actual),
    db: Session = Depends(get_db)
):
    sesiones = db.query(ChatSession).filter(ChatSession.id_usuario == usuario["id_usuario"]).all()
    session_ids = [s.id_session for s in sesiones]
    
    mensajes = db.query(ChatMessage).filter(
        ChatMessage.id_session.in_(session_ids)
    ).all()
    
    archivos_subidos = 0
    archivos_generados = 0
    for m in mensajes:
        if m.file_urls:
            if m.rol == 'user':
                archivos_subidos += len(m.file_urls)
            elif m.rol == 'jarvis':
                archivos_generados += len(m.file_urls)
                
    return {
        "archivos_subidos": archivos_subidos,
        "archivos_generados": archivos_generados
    }


@app.get("/v1/chat/sessions/{session_id}/messages")
async def obtener_mensajes(
    session_id: str,
    usuario: dict = Depends(obtener_usuario_actual),
    db: Session = Depends(get_db)
):
    sesion = db.query(ChatSession).filter(
        ChatSession.id_session == session_id,
        ChatSession.id_usuario == usuario["id_usuario"]
    ).first()
    if not sesion:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    
    mensajes = db.query(ChatMessage).filter(ChatMessage.id_session == session_id).order_by(ChatMessage.created_at.asc()).all()
    return [
        {
            "id_mensaje": m.id_mensaje,
            "rol": m.rol,
            "contenido": m.contenido,
            "file_urls": m.file_urls or [],
            "created_at": m.created_at.isoformat(),
        }
        for m in mensajes
    ]


# ============================================================
# Endpoints: Chat Multimodal Persistente con J.A.R.V.I.S.
@app.get("/v1/agent/prompt")
async def obtener_prompt_agente(
    usuario: dict = Depends(obtener_usuario_actual)
):
    perfil = usuario.get("perfil_jarvis", "Mecanico")
    prompt = SYSTEM_PROMPTS.get(perfil, SYSTEM_PROMPTS["Mecanico"])
    return {"perfil": perfil, "prompt": prompt, "todos_los_prompts": SYSTEM_PROMPTS}


# ── Gestión de documentos / mensajes con archivos ──────────────

@app.get("/v1/chat/sessions/documents/all")
async def listar_documentos(
    usuario: dict = Depends(obtener_usuario_actual),
    db: Session = Depends(get_db)
):
    """Lista todos los mensajes con archivos adjuntos del usuario."""
    sesiones = db.query(ChatSession).filter(ChatSession.id_usuario == usuario["id_usuario"]).all()
    session_map = {s.id_session: s.titulo for s in sesiones}
    session_ids = list(session_map.keys())
    mensajes_con_archivos = db.query(ChatMessage).filter(
        ChatMessage.id_session.in_(session_ids),
        ChatMessage.file_urls.isnot(None),
    ).order_by(ChatMessage.created_at.desc()).all()

    resultado = []
    for m in mensajes_con_archivos:
        urls = m.file_urls or []
        if not urls:
            continue
        for url in urls:
            tipo = "desconocido"
            if url.startswith("data:"):
                tipo = url.split(";")[0].replace("data:", "")
            elif url.startswith("http"):
                tipo = "archivo_generado"
            
            resultado.append({
                "id_mensaje": m.id_mensaje,
                "id_session": m.id_session,
                "titulo_sesion": session_map.get(m.id_session, "Conversación"),
                "contenido": m.contenido,
                "tipo": tipo,
                "rol": m.rol,
                "url": url,
                "created_at": m.created_at.isoformat(),
            })
    return resultado


@app.delete("/v1/chat/messages/{mensaje_id}")
async def eliminar_mensaje(
    mensaje_id: str,
    usuario: dict = Depends(obtener_usuario_actual),
    db: Session = Depends(get_db)
):
    """Elimina un mensaje verificando propiedad del usuario."""
    sesiones = db.query(ChatSession).filter(ChatSession.id_usuario == usuario["id_usuario"]).all()
    session_ids = [s.id_session for s in sesiones]
    mensaje = db.query(ChatMessage).filter(
        ChatMessage.id_mensaje == mensaje_id,
        ChatMessage.id_session.in_(session_ids)
    ).first()
    if not mensaje:
        raise HTTPException(status_code=404, detail="Mensaje no encontrado o sin permisos")
    db.delete(mensaje)
    db.commit()
    return {"message": "Mensaje eliminado correctamente"}


class PatchMensajeRequest(BaseModel):
    contenido: Optional[str] = None


@app.patch("/v1/chat/messages/{mensaje_id}")
async def editar_mensaje(
    mensaje_id: str,
    body: PatchMensajeRequest,
    usuario: dict = Depends(obtener_usuario_actual),
    db: Session = Depends(get_db)
):
    """Edita el contenido de un mensaje del usuario."""
    sesiones = db.query(ChatSession).filter(ChatSession.id_usuario == usuario["id_usuario"]).all()
    session_ids = [s.id_session for s in sesiones]
    mensaje = db.query(ChatMessage).filter(
        ChatMessage.id_mensaje == mensaje_id,
        ChatMessage.id_session.in_(session_ids),
        ChatMessage.rol == "user"
    ).first()
    if not mensaje:
        raise HTTPException(status_code=404, detail="Mensaje no encontrado o sin permisos")
    if body.contenido is not None:
        mensaje.contenido = body.contenido
    db.commit()
    db.refresh(mensaje)
    return {"id_mensaje": mensaje.id_mensaje, "contenido": mensaje.contenido, "updated": True}


# ── Chat: envío de mensaje principal ──────────────────────────

@app.post("/v1/chat/sessions/{session_id}/send")
async def enviar_mensaje_chat(
    session_id: str,
    mensaje: str = Form(""),
    custom_prompt: Optional[str] = Form(None),
    focused_document_ids: Optional[str] = Form(None),
    files: List[UploadFile] = File(default=[]),
    x_voice_id: Optional[str] = Header(None),
    x_sarcasm_level: Optional[str] = Header(None),
    x_custom_prompt: Optional[str] = Header(None),
    usuario: dict = Depends(obtener_usuario_actual),
    db: Session = Depends(get_db)
):
    sesion = db.query(ChatSession).filter(
        ChatSession.id_session == session_id,
        ChatSession.id_usuario == usuario["id_usuario"]
    ).first()
    if not sesion:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")

    uploaded_urls: list = []
    generated_urls: list = []
    gemini_parts: list = []
    doc_context: str = ""
    transcripcion_audio: str = ""
    audio_parts: list = []
    total_tokens = 0

    for file in files:
        if not file.filename:
            continue
        file_bytes = await file.read()
        file_type = file.content_type or "application/octet-stream"
        b64 = base64.b64encode(file_bytes).decode("utf-8")
        data_uri = f"data:{file_type};base64,{b64}"
        uploaded_urls.append(data_uri)

        if file_type.startswith("image/"):
            gemini_parts.append(types.Part.from_bytes(data=file_bytes, mime_type=file_type))

        elif file_type.startswith("audio/") or file.filename.lower().endswith((".m4a", ".mp3", ".ogg", ".wav", ".webm")):
            safe_mime = file_type if file_type.startswith("audio/") else "audio/mp4"
            audio_parts.append(types.Part.from_bytes(data=file_bytes, mime_type=safe_mime))

        elif (file_type in ("application/pdf",) or file_type.startswith("text/")
              or file.filename.lower().endswith((".pdf", ".txt", ".csv", ".md"))):
            try:
                if file_type == "application/pdf":
                    try:
                        import fitz
                        import io as _io
                        pdf_doc = fitz.open(stream=_io.BytesIO(file_bytes), filetype="pdf")
                        text = "\n".join(page.get_text() for page in pdf_doc)
                        pdf_doc.close()
                    except ImportError:
                        text = file_bytes.decode("utf-8", errors="ignore")
                else:
                    text = file_bytes.decode("utf-8", errors="ignore")
                doc_context += f"\n\n=== DOCUMENTO: {file.filename} ===\n{text[:20000]}"
            except Exception:
                pass

    # FIX #1 – Transcribir audio con Gemini
    if audio_parts:
        try:
            _gc = get_gemini_client()
            tr = _gc.models.generate_content(
                model="gemini-3.6-flash",
                contents=audio_parts + [
                    "Transcribe EXACTAMENTE lo que se dice en el audio adjunto. "
                    "Responde SOLO con el texto transcrito, sin ninguna explicación."
                ],
            )
            transcripcion_audio = (tr.text or "").strip()
            if transcripcion_audio:
                mensaje = transcripcion_audio
        except Exception as e:
            print(f"⚠️ Error transcribiendo audio: {e}")
            mensaje = mensaje or "(Audio de voz - no transcribible)"

    # FIX #2 – Recuperar documentos previos de la sesión
    mensajes_hist = db.query(ChatMessage).filter(
        ChatMessage.id_session == session_id
    ).order_by(ChatMessage.created_at.asc()).all()

    focused_ids_list = []
    if focused_document_ids:
        try:
            focused_ids_list = json.loads(focused_document_ids)
            if not isinstance(focused_ids_list, list):
                focused_ids_list = []
        except Exception:
            pass

    focused_knowledge = ""
    if focused_ids_list:
        try:
            # 1. Embed user query
            _gc = get_gemini_client()
            q_emb_resp = _gc.models.embed_content(
                model="text-embedding-004",
                contents=mensaje if mensaje else "Resumen del documento"
            )
            q_vec = q_emb_resp.embeddings[0].values
            
            # 2. Retrieve top chunks
            chunks = db.query(DocumentChunk).filter(
                DocumentChunk.id_mensaje.in_(focused_ids_list)
            ).order_by(
                DocumentChunk.embedding.cosine_distance(q_vec)
            ).limit(4).all()
            
            if chunks:
                focused_knowledge = "\n".join([f"- {c.texto}" for c in chunks])
        except Exception as e:
            print(f"Error en RAG retrieval: {e}")

    knowledge_from_history = ""
    contenido_usuario = transcripcion_audio if transcripcion_audio else (mensaje if mensaje else "(Archivo adjunto)")
    msg_user = ChatMessage(id_session=session_id, rol="user", contenido=contenido_usuario, file_urls=uploaded_urls)
    db.add(msg_user)
    db.flush()

    if doc_context.strip():
        try:
            # Simple chunking
            chunk_size = 1000
            text_chunks = [doc_context[i:i+chunk_size] for i in range(0, len(doc_context), chunk_size)]
            
            _gc = get_gemini_client()
            for i, chunk_text in enumerate(text_chunks):
                emb_resp = _gc.models.embed_content(
                    model="text-embedding-004",
                    contents=chunk_text
                )
                vec = emb_resp.embeddings[0].values
                db.add(DocumentChunk(
                    id_mensaje=msg_user.id_mensaje,
                    chunk_index=i,
                    texto=chunk_text,
                    embedding=vec
                ))
        except Exception as e:
            print(f"Error generando embeddings: {e}")

    is_superadmin = usuario.get("is_superadmin", False)
    sys_prompt = "Eres J.A.R.V.I.S., asistente virtual."
    
    if is_superadmin:
        sys_prompt = "Eres un administrador global nivel Dios. Tienes acceso total a todas las herramientas, bases de datos y configuraciones. Puedes gestionar cualquier módulo del ERP, inspecciones, IoT y MikroTik."
    else:
        active_id = usuario.get("active_profile_id")
        if active_id:
            from backend.models import JarvisProfile, TenantProfile
            jp = db.query(JarvisProfile).filter(JarvisProfile.id_perfil == active_id).first()
            if jp:
                sys_prompt = jp.instrucciones_base
                tp = db.query(TenantProfile).filter(
                    TenantProfile.id_tenant == usuario["id_tenant"],
                    TenantProfile.id_perfil == active_id
                ).first()
                if tp and tp.instrucciones_extra:
                    sys_prompt += f"\n\n[Instrucciones Adicionales del Cliente]:\n{tp.instrucciones_extra}"

    # Override temporal de la sesión (ej. de la app móvil)
    prompt_personalizado = custom_prompt
    if not prompt_personalizado and x_custom_prompt:
        try:
            prompt_personalizado = base64.b64decode(x_custom_prompt).decode("utf-8")
        except Exception:
            prompt_personalizado = x_custom_prompt
            
    if prompt_personalizado and prompt_personalizado.strip():
        sys_prompt = prompt_personalizado.strip()

    prompt_con_contexto = f"Instrucción del sistema: {sys_prompt}\n"
    if x_sarcasm_level:
        prompt_con_contexto += f"Nota: Mantén un nivel de sarcasmo/ironía: {x_sarcasm_level}.\n"
    prompt_con_contexto += "\n"
    if focused_knowledge:
        prompt_con_contexto += f"[DOCUMENTOS SELECCIONADOS COMO FOCO PRINCIPAL]\n(Instrucción: El usuario te pide que te enfoques PRINCIPALMENTE en estos documentos para responder)\n{focused_knowledge}\n\n"
    if knowledge_from_history:
        prompt_con_contexto += f"[CONOCIMIENTO DE DOCUMENTOS PREVIOS EN ESTA SESIÓN]{knowledge_from_history}\n\n"
    if doc_context:
        prompt_con_contexto += f"[DOCUMENTOS ADJUNTOS EN ESTE MENSAJE]\n(Instrucción: Analiza el siguiente contenido para generar la respuesta. No lo ignores.)\n{doc_context}\n\n"
    if gemini_parts:
        prompt_con_contexto += (
            "[IMÁGENES ADJUNTAS]\n"
            "(Instrucción IMPORTANTE: El usuario ha adjuntado una o más imágenes. "
            "Analiza visualmente cada imagen en detalle. Extrae TODO el contenido relevante: "
            "texto, números, tablas, diagramas, esquemas, gráficos, fórmulas, código, "
            "etiquetas, señales, y cualquier otra información visible. "
            "Si la imagen contiene un diagrama técnico o arquitectónico, describe su estructura. "
            "Si contiene datos tabulares, organízalos en formato de tabla. "
            "Incluye esta información extraída como parte de tu respuesta.)\n\n"
        )
    for h in mensajes_hist[-6:]:
        prompt_con_contexto += f"{h.rol.capitalize()}: {h.contenido}\n"
    prompt_con_contexto += f"User: {mensaje if mensaje else '(sin texto adicional)'}\nJARVIS:"

    user_db = db.query(Usuario).filter(Usuario.id_usuario == usuario["id_usuario"]).first()
    if not user_db:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    from backend.ai_service import call_llm_with_tools
    respuesta_jarvis, t_tokens = call_llm_with_tools(db, user_db, prompt_con_contexto, uploaded_urls, generated_urls)
    total_tokens += t_tokens

    msg_jarvis = ChatMessage(id_session=session_id, rol="jarvis", contenido=respuesta_jarvis, file_urls=generated_urls)
    db.add(msg_jarvis)

    texto_titulo = transcripcion_audio if transcripcion_audio else mensaje
    if (sesion.titulo == "Nueva Conversación" or not sesion.titulo) and texto_titulo:
        sesion.titulo = texto_titulo[:35] + ("..." if len(texto_titulo) > 35 else "")

    sesion.updated_at = func.now()
    if total_tokens > 0:
        db_usuario = db.query(Usuario).filter(Usuario.id_usuario == usuario["id_usuario"]).first()
        if db_usuario:
            db_usuario.tokens_consumidos += total_tokens
    db.commit()
    db.refresh(msg_jarvis)
    db.refresh(msg_user)

    audio_b64 = ""
    try:
        vid = x_voice_id if x_voice_id else os.getenv("ELEVENLABS_VOICE_ID", "pNInz6obbfDQGcgMyIGb")
        ar = get_elevenlabs_client().generate(text=respuesta_jarvis, voice=vid, model="eleven_multilingual_v2", voice_settings=VoiceSettings(stability=0.30, similarity_boost=0.75, style=0.0, use_speaker_boost=True))
        audio_b64 = base64.b64encode(b"".join(ar)).decode("utf-8")
    except Exception as tts_err:
        print(f"⚠️ Error TTS: {tts_err}")

    return {
        "id_mensaje": msg_jarvis.id_mensaje,
        "id_mensaje_usuario": msg_user.id_mensaje,
        "rol": msg_jarvis.rol,
        "contenido": msg_jarvis.contenido,
        "transcripcion_usuario": transcripcion_audio,
        "file_urls": msg_jarvis.file_urls or [],
        "audio_base64": audio_b64,
        "created_at": msg_jarvis.created_at.isoformat(),
    }



# ============================================================
# Endpoints: Configuracion IoT
# ============================================================
from pydantic import BaseModel

class IoTConfigSchema(BaseModel):
    ha_url: str | None = None
    ha_token: str | None = None
    mqtt_broker: str | None = None
    mqtt_port: int = 1883
    mqtt_user: str | None = None
    mqtt_password: str | None = None

@app.get("/v1/iot/config")
async def get_iot_config(
    usuario: dict = Depends(obtener_usuario_actual),
    db: Session = Depends(get_db)
):
    from backend.models import IoTConfig
    config = db.query(IoTConfig).filter(IoTConfig.id_usuario == usuario["id_usuario"]).first()
    if not config:
        return {}
    return {
        "ha_url": config.ha_url,
        "ha_token": config.ha_token,
        "mqtt_broker": config.mqtt_broker,
        "mqtt_port": config.mqtt_port,
        "mqtt_user": config.mqtt_user,
        "mqtt_password": config.mqtt_password
    }

@app.post("/v1/iot/config")
async def update_iot_config(
    body: IoTConfigSchema,
    usuario: dict = Depends(obtener_usuario_actual),
    db: Session = Depends(get_db)
):
    from backend.models import IoTConfig
    config = db.query(IoTConfig).filter(IoTConfig.id_usuario == usuario["id_usuario"]).first()
    if not config:
        config = IoTConfig(id_usuario=usuario["id_usuario"])
        db.add(config)
    
    config.ha_url = body.ha_url
    config.ha_token = body.ha_token
    config.mqtt_broker = body.mqtt_broker
    config.mqtt_port = body.mqtt_port
    config.mqtt_user = body.mqtt_user
    config.mqtt_password = body.mqtt_password
    
    db.commit()
    return {"message": "Configuración IoT guardada"}

