with open('backend/main.py', 'r', encoding='utf-8') as f:
    content = f.read()

import re

# We need to replace the mangled obtener_mensajes and everything around it 
# up to pipeline_enfermera with the correct blocks for pipeline_inspector and obtener_mensajes.

bad_block = """@app.get("/v1/chat/sessions/{session_id}/messages")
async def obtener_mensajes(
    session_id: str,
    usuario: dict = Depends(obtener_usuario_actual),
    db: Session = Depends(get_db)
):
    sesion = db.query(ChatSession).filter(
        ChatSession.id_session == session_id,
            f"Gravedad: {parsed.gravedad}\n"
            f"Acción: {parsed.accion_recomendada}"
        )
    
    return respuesta"""

good_block = """@app.post("/v1/jarvis/inspector/procesar-completo", response_model=JarvisResponse)
async def pipeline_inspector(
    audio_file: UploadFile = File(...),
    usuario: dict = Depends(requiere_feature("modulo_inspeccion")),
):
    \"\"\"Pipeline para perfil Inspector Fiscal DGC con extracción estructurada.\"\"\"
    contexto = (
        "(IMPORTANTE: Extrae tipo de infracción, descripción del hallazgo, normativa aplicable, "
        "gravedad (Leve/Grave/Gravísima) y acción recomendada. Genera un resumen profesional en 'mensaje_para_usuario'.)"
    )
    respuesta, parsed = await _pipeline_ia(audio_file, "Inspector_DGC", contexto, response_format=RespuestaInspector)
    
    if parsed:
        respuesta.diagnostico_ia = (
            f"Tipo: {parsed.tipo_infraccion}\\n"
            f"Hallazgo: {parsed.descripcion_hallazgo}\\n"
            f"Normativa: {parsed.normativa_aplicable}\\n"
            f"Gravedad: {parsed.gravedad}\\n"
            f"Acción: {parsed.accion_recomendada}"
        )
    
    return respuesta

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
    ]"""

if bad_block in content:
    content = content.replace(bad_block, good_block)
    with open('backend/main.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("RESTORED CORRECTLY")
else:
    print("BAD BLOCK NOT FOUND")
