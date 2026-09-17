# ============================================================
# 1) Agregar a SYSTEM_PROMPTS (junto a Mecanico, Inspector_DGC, Enfermera_Paliativos)
# ============================================================

SYSTEM_PROMPTS_ADDITION = {
    "Ingeniero_Redes": (
        "Eres J.A.R.V.I.S., asistente virtual de un ingeniero en conectividad, redes y "
        "telecomunicaciones, certificado MikroTik (MTCNA/MTCRE/MTCINE) y experto en la API "
        "REST de RouterOS. Eres británico, educado y técnicamente preciso. Dirígete al "
        "usuario como 'Señor Ingeniero'. "
        "Tu especialidad incluye:\n"
        "- Diagnóstico de fallas en redes MikroTik (PPPoE, VLAN, firewall, routing, QoS, wireless)\n"
        "- Redacción de comandos RouterOS (CLI y llamadas a la API REST /rest/) para aplicar cambios\n"
        "- Análisis de topologías de red ISP (core routers, CPEs, enlaces backhaul, OLT/ONU)\n"
        "- Hardening de seguridad de dispositivos MikroTik (firewall rules, RouterOS API access, "
        "  servicios expuestos)\n"
        "- Troubleshooting de clientes PPPoE caídos, saturación de ancho de banda y calidad de enlace\n"
        "Responde con rigor técnico, usando terminología de networking correcta (VLAN, MPLS, BGP, "
        "OSPF, mangle, NAT, etc.) y, cuando corresponda, propone el comando RouterOS exacto o el "
        "endpoint de la API REST (método HTTP + path + body JSON) necesario para resolver el problema."
    ),
}

# ============================================================
# 2) Schema de extracción estructurada
# ============================================================

class RespuestaIngenieroRedes(BaseModel):
    """Esquema de extracción estructurada para el perfil Ingeniero de Redes MikroTik."""
    transcripcion_usuario: str
    dispositivo_afectado: str          # ej. "CCR2004 - Core Puerto Varas" / "CPE cliente 192.168.10.5"
    diagnostico_tecnico: str           # causa raíz probable
    severidad: str                     # Baja, Media, Alta, Crítica
    comando_routeros: str | None = None      # comando CLI de RouterOS sugerido, si aplica
    endpoint_api_rest: str | None = None     # ej. "POST /rest/interface/pppoe-server/remove"
    accion_recomendada: str
    mensaje_para_usuario: str


# ============================================================
# 3) Función de pipeline
# ============================================================

async def _pipeline_ingeniero_redes(audio_file: UploadFile, usuario: dict):
    """Pipeline para perfil Ingeniero de Conectividad y Redes MikroTik."""
    contexto = (
        "(IMPORTANTE: Extrae el dispositivo o segmento de red afectado, diagnóstico técnico, "
        "severidad (Baja/Media/Alta/Crítica), el comando RouterOS exacto si aplica, el endpoint "
        "de la API REST de MikroTik (método + path + body) si aplica, y una acción recomendada. "
        "Genera un resumen técnico claro en 'mensaje_para_usuario'.)"
    )
    respuesta, parsed = await _pipeline_ia(
        audio_file, "Ingeniero_Redes", contexto, response_format=RespuestaIngenieroRedes
    )

    if parsed:
        respuesta.diagnostico_ia = (
            f"Dispositivo: {parsed.dispositivo_afectado}\n"
            f"Diagnóstico: {parsed.diagnostico_tecnico}\n"
            f"Severidad: {parsed.severidad}\n"
            + (f"Comando RouterOS: {parsed.comando_routeros}\n" if parsed.comando_routeros else "")
            + (f"API REST: {parsed.endpoint_api_rest}\n" if parsed.endpoint_api_rest else "")
            + f"Acción: {parsed.accion_recomendada}"
        )

    return respuesta


# ============================================================
# 4) Endpoint
# ============================================================

@app.post("/v1/jarvis/redes/procesar-completo", response_model=JarvisResponse)
async def pipeline_ingeniero_redes(
    audio_file: UploadFile = File(...),
    usuario: dict = Depends(requiere_feature("modulo_redes")),
):
    """Pipeline para perfil Ingeniero de Conectividad y Redes MikroTik."""
    return await _pipeline_ingeniero_redes(audio_file, usuario)
