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
import tempfile
import hashlib
import hmac
from typing import Type
from contextlib import asynccontextmanager

from fastapi import (
    FastAPI, UploadFile, File, Form, Depends, HTTPException, Request, Response,
)
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google import genai
from google.genai import types
from elevenlabs.client import ElevenLabs as ElevenLabsClient
from sqlalchemy.orm import Session

from backend.database import get_db, inicializar_base_de_datos_remota
from backend.auth import router as auth_router, obtener_usuario_actual, requiere_feature
from backend.models import OrdenTrabajo


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
        "Eres J.A.R.V.I.S., asistente virtual de un taller mecánico automotriz. "
        "Eres británico, educado y sutilmente irónico. Dirígete al usuario como 'Señor'. "
        "Tu especialidad incluye:\n"
        "- Diagnóstico mecánico y eléctrico de vehículos\n"
        "- Gestión de órdenes de trabajo (OT)\n"
        "- Cotización de repuestos y mano de obra\n"
        "- Seguimiento de estado de reparaciones\n"
        "Responde de forma técnica, concisa y proactiva. Si detectas un problema potencial, sugiérelo."
    ),
    "Inspector_DGC": (
        "Eres J.A.R.V.I.S., asistente virtual de inspección fiscal para la Dirección General de Consumo. "
        "Eres británico, educado y preciso. Dirígete al usuario como 'Señor Inspector'. "
        "Tu especialidad incluye:\n"
        "- Verificación de cumplimiento normativo en establecimientos comerciales\n"
        "- Redacción de actas de inspección y observaciones\n"
        "- Consulta de regulaciones vigentes\n"
        "- Seguimiento de procesos sancionatorios\n"
        "Responde con rigor legal y citando normativa cuando corresponda."
    ),
    "Enfermera_Paliativos": (
        "Eres J.A.R.V.I.S., asistente virtual de enfermería en cuidados paliativos. "
        "Eres británico, educado y empático. Dirígete al usuario según su género. "
        "Tu especialidad incluye:\n"
        "- Registro de signos vitales y síntomas del paciente\n"
        "- Protocolos de manejo del dolor (escala EVA/NRS)\n"
        "- Coordinación de cuidados y medicación\n"
        "- Soporte emocional y comunicación con familias\n"
        "Responde con calidez profesional, priorizando siempre el bienestar del paciente."
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
            model='gemini-2.0-flash',
            contents=[audio_part, prompt_text],
            config=types.GenerateContentConfig(**config_args),
        )

        import json
        if response_format:
            parsed_data = response_format.model_validate_json(respuesta_gemini.text)
            respuesta_texto = getattr(parsed_data, "mensaje_para_usuario", "")
            texto_usuario = getattr(parsed_data, "transcripcion_usuario", "")
        else:
            data = json.loads(respuesta_gemini.text)
            respuesta_texto = data.get("mensaje_para_usuario", "")
            texto_usuario = data.get("transcripcion_usuario", "")
            parsed_data = None

        # 3. Text-to-Speech con ElevenLabs
        voice_id = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
        audio_response = get_elevenlabs_client().generate(
            text=respuesta_texto,
            voice=voice_id,
            model="eleven_multilingual_v2",
        )
        audio_tts = b"".join(audio_response)
        audio_b64 = base64.b64encode(audio_tts).decode("utf-8")

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
    """Pipeline para perfil Inspector Fiscal DGC."""
    respuesta, _ = await _pipeline_ia(audio_file, "Inspector_DGC")
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
        import json
        payload = json.loads(payload_bytes)
        data_id = str(payload.get("data", {}).get("id", ""))
        manifest = f"id:{data_id};request-id:{x_request_id};ts:{ts};"

        expected = hmac.new(
            MP_WEBHOOK_SECRET.encode(), manifest.encode(), hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(v1, expected):
            raise HTTPException(status_code=403, detail="Firma de webhook inválida.")
    else:
        import json
        payload = json.loads(payload_bytes)

    # Procesar evento de pago
    action = payload.get("action", "")
    if action == "payment.created":
        payment_id = payload.get("data", {}).get("id", "desconocido")
        print(f"[MercadoPago] Pago creado: {payment_id}")

    return Response(content="OK", status_code=200)


# ============================================================
# Health Check (para Docker HEALTHCHECK y monitoring)
# ============================================================

@app.get("/health")
async def health():
    """Endpoint de salud para verificar que el servicio está activo."""
    return {"status": "ok", "service": "J.A.R.V.I.S. Core Engine", "version": "1.0.0"}
