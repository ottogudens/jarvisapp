with open('backend/main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Update chunk size
content = content.replace("text[:10000]", "text[:20000]")

# Add explicit instructions for attached docs
old_doc_instruct = "if doc_context:\n        prompt_con_contexto += f\"[DOCUMENTOS ADJUNTOS EN ESTE MENSAJE]{doc_context}\\n\\n\""
new_doc_instruct = """if doc_context:
        prompt_con_contexto += f"[DOCUMENTOS ADJUNTOS EN ESTE MENSAJE]\\n(Instrucción: Analiza el siguiente contenido para generar la respuesta. No lo ignores.)\\n{doc_context}\\n\\n\""""
content = content.replace(old_doc_instruct, new_doc_instruct)

# Now inject the Supabase Document Generation Tool
tool_code = """        def enviar_mensaje_mqtt(topic: str, payload: str) -> str:
            \"\"\"Publica un mensaje JSON en MQTT para controlar dispositivos locales.\"\"\"
            return iot_service.publicar_mensaje_mqtt(topic, payload)

        def generar_documento(titulo: str, contenido: str, formato: str = "txt") -> str:
            \"\"\"Genera un documento (txt, md, o pdf) y lo guarda permanentemente, devolviendo la URL.\"\"\"
            import os, uuid
            from supabase import create_client, Client
            try:
                url = os.getenv("SUPABASE_URL")
                key = os.getenv("SUPABASE_KEY")
                if not url or not key:
                    return "Error: Supabase no está configurado."
                supabase: Client = create_client(url, key)
                
                filename = f"{uuid.uuid4()}.{formato}"
                # Guardar temporal
                path = f"/tmp/{filename}"
                with open(path, "w", encoding="utf-8") as file:
                    file.write(contenido)
                
                with open(path, "rb") as file:
                    res = supabase.storage.from_("jarvis-files").upload(filename, file)
                
                public_url = supabase.storage.from_("jarvis-files").get_public_url(filename)
                
                # Adjuntar la URL a la variable global uploaded_urls para que se guarde en la BD
                uploaded_urls.append(public_url)
                
                return f"Documento '{titulo}' generado y guardado exitosamente. URL: {public_url}"
            except Exception as e:
                return f"Fallo al guardar el documento: {str(e)}"
"""

content = content.replace(
    "        def enviar_mensaje_mqtt(topic: str, payload: str) -> str:\n            \"\"\"Publica un mensaje JSON en MQTT para controlar dispositivos locales.\"\"\"\n            return iot_service.publicar_mensaje_mqtt(topic, payload)",
    tool_code
)

# Update tools list in generate_content
content = content.replace(
    "tools=[obtener_estado_dispositivo, activar_dispositivo, enviar_mensaje_mqtt],",
    "tools=[obtener_estado_dispositivo, activar_dispositivo, enviar_mensaje_mqtt, generar_documento],"
)

with open('backend/main.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated document context and added Supabase tool.")
