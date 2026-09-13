import os
with open('backend/main.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('from openai import OpenAI', 'from google import genai\\nfrom google.genai import types')
content = content.replace('_client_openai = None', '_client_gemini = None')

old_func = '''def get_openai_client() -> OpenAI:
    global _client_openai
    if _client_openai is None:
        _client_openai = OpenAI()
    return _client_openai'''

new_func = '''def get_gemini_client():
    global _client_gemini
    if _client_gemini is None:
        _client_gemini = genai.Client(api_key=os.getenv("GEMINI_API_KEY", ""))
    return _client_gemini'''

content = content.replace(old_func, new_func)

old_pipeline = '''async def _pipeline_ia(
    audio_file: UploadFile,
    perfil: str,
    contexto_extra: str = "",
    response_format: Type[BaseModel] | None = None,
) -> tuple[JarvisResponse, BaseModel | None]:'''

# We will cut the string from old_pipeline to the end of the function and replace it.
import re
match = re.search(r'async def _pipeline_ia.*?return response_obj, parsed_data\n\n    finally:.*?os\.unlink\(ruta_temp\)', content, re.DOTALL)
if match:
    new_pipeline = '''async def _pipeline_ia(
    audio_file: UploadFile,
    perfil: str,
    contexto_extra: str = "",
    response_format: Type[BaseModel] | None = None,
) -> tuple[JarvisResponse, BaseModel | None]:
    suffix = os.path.splitext(audio_file.filename or "audio.m4a")[1] or ".m4a"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        contenido = await audio_file.read()
        tmp.write(contenido)
        ruta_temp = tmp.name

    try:
        system_prompt = SYSTEM_PROMPTS.get(perfil, SYSTEM_PROMPTS["Mecanico"])
        if contexto_extra:
            system_prompt += f"\\n\\nContexto operativo actual:\\n{contexto_extra}"

        # Gemini 1.5 Flash supports audio + text prompt
        client = get_gemini_client()
        
        with open(ruta_temp, "rb") as f:
            audio_bytes = f.read()
            
        audio_part = types.Part.from_bytes(data=audio_bytes, mime_type="audio/mp4")
        
        prompt_text = (
            "Transcribe el audio adjunto e incluye la transcripcion en el campo 'transcripcion_usuario' de la respuesta JSON. "
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
            model='gemini-1.5-flash',
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

        # Text-to-Speech con ElevenLabs
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

    finally:
        if os.path.exists(ruta_temp):
            os.unlink(ruta_temp)'''
    content = content[:match.start()] + new_pipeline + content[match.end():]

# Actualizar el esquema de RespuestaMecanico para que incluya transcripcion_usuario
old_schema = '''class RespuestaMecanico(BaseModel):
    """Esquema de extracción estructurada para el perfil Mecánico."""
    diagnostico_tecnico: str
    repuestos_requeridos: list[str]
    estado_sugerido: str
    mensaje_para_usuario: str'''
new_schema = '''class RespuestaMecanico(BaseModel):
    """Esquema de extracción estructurada para el perfil Mecánico."""
    transcripcion_usuario: str
    diagnostico_tecnico: str
    repuestos_requeridos: list[str]
    estado_sugerido: str
    mensaje_para_usuario: str'''
content = content.replace(old_schema, new_schema)

with open('backend/main.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Done")
