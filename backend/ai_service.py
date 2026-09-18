import os
import json
import asyncio
import litellm
from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.models import Tenant, SystemSettings, AIUsageStats
from backend.iot_service import IoTService
from backend.mikrotik_tools import obtener_estado_red_mikrotik, listar_interfaces_mikrotik, ver_clientes_dhcp_mikrotik, comando_mikrotik_avanzado

# Configurar herramientas para litellm
LITELLM_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "obtener_estado_dispositivo",
            "description": "Obtiene el estado de un dispositivo en Home Assistant.",
            "parameters": {
                "type": "object",
                "properties": {"entity_id": {"type": "string", "description": "ID del dispositivo"}},
                "required": ["entity_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "activar_dispositivo",
            "description": "Cambia estado de un dispositivo en Home Assistant (ej. turn_on, turn_off).",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_id": {"type": "string", "description": "ID del dispositivo"},
                    "accion": {"type": "string", "description": "Acción a realizar"}
                },
                "required": ["entity_id", "accion"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "enviar_mensaje_mqtt",
            "description": "Publica un mensaje JSON en MQTT para controlar dispositivos locales.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "Topic MQTT"},
                    "payload": {"type": "string", "description": "Payload JSON"}
                },
                "required": ["topic", "payload"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generar_documento",
            "description": "Genera un documento (txt, md, o pdf) y lo guarda permanentemente, devolviendo la URL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "titulo": {"type": "string", "description": "Título del documento"},
                    "contenido": {"type": "string", "description": "Contenido del documento"},
                    "formato": {"type": "string", "description": "Formato (txt, md, pdf)"}
                },
                "required": ["titulo", "contenido"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "obtener_estado_red_mikrotik",
            "description": "Verifica el estado de red de los routers MikroTik y realiza pings.",
            "parameters": {
                "type": "object",
                "properties": {
                    "id_router": {"type": "integer", "description": "ID del router."},
                    "ping_target": {"type": "string", "description": "Dirección IP o dominio a hacer ping."}
                },
                "required": ["id_router"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "listar_interfaces_mikrotik",
            "description": "Lista las interfaces de un router MikroTik.",
            "parameters": {
                "type": "object",
                "properties": {
                    "id_router": {"type": "integer", "description": "ID del router."},
                    "filter_name": {"type": "string", "description": "Filtrar por nombre de interfaz."}
                },
                "required": ["id_router"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ver_clientes_dhcp_mikrotik",
            "description": "Obtiene la lista de clientes conectados (DHCP Leases) en un router MikroTik.",
            "parameters": {
                "type": "object",
                "properties": {"id_router": {"type": "integer", "description": "ID del router"}},
                "required": ["id_router"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "comando_mikrotik_avanzado",
            "description": (
                "Ejecuta un comando raw en la API REST del router MikroTik (ej: /ip/address/print). "
                "Si el comando MODIFICA el router (rutas terminadas en /add, /set, /remove, /enable, "
                "/disable, /move, o acciones como /reboot, /shutdown, /backup/load, "
                "/routerboard/upgrade), la primera llamada SIEMPRE devuelve una vista previa "
                "sin ejecutar nada. Debes mostrar el comando exacto al usuario, esperar su "
                "confirmación explícita en el chat, y solo entonces volver a llamar esta función "
                "con confirmar=true para ejecutarlo de verdad. Nunca pases confirmar=true sin que "
                "el usuario haya aprobado explícitamente el comando en su mensaje anterior."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "comando": {"type": "string", "description": "Comando API (ej. /ip/route/print)"},
                    "id_router": {"type": "integer"},
                    "parametros": {"type": "object", "description": "Body/filtros del comando, si aplica"},
                    "confirmar": {
                        "type": "boolean",
                        "description": "Solo true si el usuario ya aprobó explícitamente ejecutar este comando destructivo. Por defecto false."
                    }
                },
                "required": ["comando"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "almacenar_conocimiento",
            "description": "Almacena el texto extraído de los archivos subidos en este turno como un documento en la memoria RAG del agente. Úsalo SIEMPRE que el usuario envíe un archivo y te pida explícitamente guardarlo, o cuando creas que es un documento importante que debe persistir para futuras consultas. Se almacenará el texto completo de todos los archivos enviados en este mensaje bajo el nombre que indiques.",
            "parameters": {
                "type": "object",
                "properties": {
                    "nombre_documento": {"type": "string", "description": "Nombre o título para guardar el documento. Usa el nombre solicitado por el usuario o infiere uno a partir del contenido."}
                },
                "required": ["nombre_documento"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "buscar_conocimiento",
            "description": "Busca fragmentos de información en la memoria de documentos previamente guardada por el cliente. Úsalo si el usuario pregunta sobre algo que no sabes, pero que pudo haber sido subido como documento o minuta en el pasado.",
            "parameters": {
                "type": "object",
                "properties": {
                    "consulta": {"type": "string", "description": "Pregunta detallada o palabras clave para buscar por similitud semántica en la base de documentos del cliente."}
                },
                "required": ["consulta"]
            }
        }
    }
]

def load_ai_keys(db: Session):
    keys = db.query(SystemSettings).filter(SystemSettings.key.in_(
        ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "DEEPSEEK_API_KEY", "GEMINI_API_KEY"]
    )).all()
    for k in keys:
        if k.value:
            os.environ[k.key] = k.value

def call_llm_with_tools(
    db: Session,
    user_db,
    sys_prompt: str,
    prompt_con_contexto: str,
    uploaded_urls: list,
    generated_urls: list,
    raw_documents: list = None
):
    # Cargar keys
    load_ai_keys(db)

    # Determinar proveedor y modelo
    tenant = db.query(Tenant).filter(Tenant.id_tenant == user_db.id_tenant).first()
    ai_provider = tenant.ai_provider if tenant else "gemini"
    ai_model = tenant.ai_model if tenant else "gemini-1.5-flash"
    
    # Adaptar prefijos de modelo para litellm
    model_name = ai_model
    if ai_provider.lower() == "gemini" and not model_name.startswith("gemini/"):
        model_name = f"gemini/{model_name}"
    elif ai_provider.lower() == "deepseek" and not model_name.startswith("deepseek/"):
        model_name = f"deepseek/{model_name}"
    elif (ai_provider.lower() == "anthropic" or ai_provider.lower() == "claude") and not model_name.startswith("anthropic/"):
        model_name = f"anthropic/{model_name}"
    elif ai_provider.lower() == "openai" and not model_name.startswith("openai/"):
        model_name = f"openai/{model_name}"

    # Construir mensajes
    content_list = [{"type": "text", "text": prompt_con_contexto}]
    for url in uploaded_urls:
        if url.startswith("data:image/"):
            content_list.append({"type": "image_url", "image_url": {"url": url}})
    
    # Fix #tokens-2: el system prompt va en su propio mensaje "system", separado
    # del contenido variable del turno. Esto permite que Gemini/Anthropic/OpenAI
    # cacheen ese prefijo estable entre turnos de la misma sesión en vez de
    # retokenizarlo completo cada vez (prompt/context caching nativo del proveedor).
    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": content_list},
    ]

    iot_service = IoTService(db, user_db.id_usuario)

    def ejecutar_herramienta(fn_name: str, args: dict) -> str:
        try: loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        if fn_name == "obtener_estado_dispositivo":
            return loop.run_until_complete(iot_service.obtener_estado_dispositivo(**args))
        elif fn_name == "activar_dispositivo":
            return loop.run_until_complete(iot_service.activar_dispositivo(**args))
        elif fn_name == "enviar_mensaje_mqtt":
            return iot_service.publicar_mensaje_mqtt(**args)
        elif fn_name == "generar_documento":
            import base64
            try:
                contenido = args.get("contenido", "")
                formato = args.get("formato", "txt").lower()
                titulo = args.get("titulo", "Documento")
                
                mime_type = "text/plain"
                if formato == "csv": mime_type = "text/csv"
                elif formato == "md": mime_type = "text/markdown"
                elif formato == "html": mime_type = "text/html"
                
                b64 = base64.b64encode(contenido.encode("utf-8")).decode("utf-8")
                data_uri = f"data:{mime_type};base64,{b64}"
                generated_urls.append(data_uri)
                return f"Documento '{titulo}' generado exitosamente."
            except Exception as e:
                return f"Error al generar documento: {str(e)}"
        elif fn_name == "obtener_estado_red_mikrotik":
            return obtener_estado_red_mikrotik(**args)
        elif fn_name == "listar_interfaces_mikrotik":
            return listar_interfaces_mikrotik(**args)
        elif fn_name == "ver_clientes_dhcp_mikrotik":
            return ver_clientes_dhcp_mikrotik(**args)
        elif fn_name == "comando_mikrotik_avanzado":
            return comando_mikrotik_avanzado(**args)
        elif fn_name == "almacenar_conocimiento":
            from backend.models import KnowledgeDocument, DocumentChunk
            nombre_doc = args.get("nombre_documento", "Documento sin título")
            if not raw_documents:
                return "Error: No se encontró ningún archivo subido en este mensaje para almacenar."
            
            texto_completo = "\n\n".join([d['text'] for d in raw_documents if d['text']])
            if not texto_completo.strip() or texto_completo.startswith("[Error"):
                return "Error: El archivo subido no contenía texto extraíble."

            try:
                nuevo_doc = KnowledgeDocument(
                    id_tenant=user_db.id_tenant,
                    id_usuario=user_db.id_usuario,
                    nombre=nombre_doc
                )
                db.add(nuevo_doc)
                db.commit()
                db.refresh(nuevo_doc)
                
                import textwrap
                partes = textwrap.wrap(texto_completo, width=1000, replace_whitespace=False)
                
                for idx, parte in enumerate(partes):
                    from litellm import embedding
                    try:
                        emb_model = "text-embedding-3-small"
                        if ai_provider.lower() == "gemini":
                            emb_model = "gemini/text-embedding-004"
                        emb_res = embedding(model=emb_model, input=[parte])
                        vector = emb_res.data[0]['embedding']
                    except Exception as e:
                        return f"Error al generar vector de embeddings: {str(e)}"
                    
                    chk = DocumentChunk(
                        id_document=nuevo_doc.id_document,
                        chunk_index=idx,
                        texto=parte,
                        embedding=vector
                    )
                    db.add(chk)
                
                db.commit()
                return f"Éxito: Documento '{nombre_doc}' almacenado correctamente en la base de conocimiento permanente con {len(partes)} fragmentos."
            except Exception as e:
                db.rollback()
                return f"Error al almacenar el conocimiento: {str(e)}"
                
        elif fn_name == "buscar_conocimiento":
            from backend.models import DocumentChunk, KnowledgeDocument
            consulta = args.get("consulta", "")
            if not consulta: return "Error: consulta vacía."
            
            from litellm import embedding
            try:
                emb_model = "text-embedding-3-small"
                if ai_provider.lower() == "gemini":
                    emb_model = "gemini/text-embedding-004"
                emb_res = embedding(model=emb_model, input=[consulta])
                vector_q = emb_res.data[0]['embedding']
            except Exception as e:
                return f"Error al generar embedding para la consulta: {str(e)}"
                
            try:
                resultados = db.query(DocumentChunk, KnowledgeDocument.nombre).join(
                    KnowledgeDocument, DocumentChunk.id_document == KnowledgeDocument.id_document
                ).filter(
                    KnowledgeDocument.id_tenant == user_db.id_tenant
                ).order_by(
                    DocumentChunk.embedding.cosine_distance(vector_q)
                ).limit(5).all()
                
                if not resultados:
                    return "No se encontraron documentos relevantes en la base de conocimiento."
                
                resp = "Resultados encontrados en la memoria de conocimiento:\n\n"
                for i, (chunk, nombre_doc) in enumerate(resultados):
                    resp += f"--- Extracto de: {nombre_doc} ---\n{chunk.texto}\n\n"
                return resp
            except Exception as e:
                return f"Error en la base de datos al buscar: {str(e)}"

        return "Herramienta desconocida"

    total_tokens = 0
    try:
        MAX_ITERATIONS = 5
        iteration = 0
        
        while iteration < MAX_ITERATIONS:
            response = litellm.completion(
                model=model_name,
                messages=messages,
                tools=LITELLM_TOOLS,
                temperature=0.7,
                max_tokens=1500,  # Fix #tokens-1: techo de costo por respuesta
            )
            if response.usage:
                total_tokens += response.usage.total_tokens

            message = response.choices[0].message
            
            if message.tool_calls:
                messages.append(message)
                
                for tool_call in message.tool_calls:
                    fn_name = tool_call.function.name
                    args = json.loads(tool_call.function.arguments)
                    res = ejecutar_herramienta(fn_name, args)
                    
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": fn_name,
                        "content": str(res)
                    })
                iteration += 1
            else:
                respuesta_jarvis = message.content or "Entendido."
                break
                
        if iteration >= MAX_ITERATIONS:
            respuesta_jarvis = "He analizado demasiados datos técnicos y me he detenido por seguridad. " + (message.content or "")

    except Exception as e:
        respuesta_jarvis = f"Señor, he experimentado un fallo en la IA ({ai_provider}): {str(e)}"

    if total_tokens > 0:
        stat = db.query(AIUsageStats).filter(
            AIUsageStats.id_tenant == user_db.id_tenant,
            AIUsageStats.proveedor == ai_provider
        ).first()
        if stat:
            stat.tokens_consumidos += total_tokens
            stat.solicitudes_realizadas += 1
        else:
            stat = AIUsageStats(
                id_tenant=user_db.id_tenant,
                proveedor=ai_provider,
                tokens_consumidos=total_tokens,
                solicitudes_realizadas=1
            )
            db.add(stat)
        db.commit()

    return respuesta_jarvis, total_tokens
