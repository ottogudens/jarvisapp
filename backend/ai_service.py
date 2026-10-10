import os
import json
import asyncio
import hashlib
import litellm
from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.models import Tenant, SystemSettings, AIUsageStats
from backend.iot_service import IoTService
from backend.mikrotik_tools import obtener_estado_red_mikrotik, listar_interfaces_mikrotik, ver_clientes_dhcp_mikrotik, comando_mikrotik_avanzado
from backend.crypto_utils import decrypt_secret

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
                "Las operaciones que mutan la configuración están deshabilitadas temporalmente. "
                "Solo úsala para diagnóstico de lectura."
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
    },
    {
        "type": "function",
        "function": {
            "name": "listar_carpetas_documentales",
            "description": "Lista los proyectos y carpetas documentales del cliente con sus IDs. Úsala antes de mover documentos, seleccionar un proyecto o crear una subcarpeta.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "crear_carpeta_documental",
            "description": "Crea un proyecto o carpeta documental. Úsala solamente cuando el usuario lo haya pedido explícitamente o confirmado de forma inequívoca.",
            "parameters": {
                "type": "object",
                "properties": {
                    "nombre": {"type": "string", "description": "Nombre del proyecto o carpeta."},
                    "parent_id": {"type": "string", "description": "ID de la carpeta/proyecto padre; omitir para crear un proyecto raíz."}
                },
                "required": ["nombre"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "mover_documento_a_carpeta",
            "description": "Mueve un documento existente a una carpeta. Úsala sólo con una instrucción explícita del usuario; consulta las carpetas primero para obtener IDs válidos.",
            "parameters": {
                "type": "object",
                "properties": {
                    "document_id": {"type": "string"},
                    "folder_id": {"type": "string"}
                },
                "required": ["document_id", "folder_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "seleccionar_carpeta_documental",
            "description": "Establece el proyecto/carpeta activo para esta conversación. Las búsquedas posteriores se limitarán a esa carpeta y sus subcarpetas. Úsala cuando el usuario pida trabajar en un proyecto específico.",
            "parameters": {
                "type": "object",
                "properties": {"folder_id": {"type": "string", "description": "ID de proyecto/carpeta. Usa cadena vacía para volver a toda la biblioteca."}},
                "required": ["folder_id"]
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
            os.environ[k.key] = decrypt_secret(k.value)

def call_llm_with_tools(
    db: Session,
    user_db,
    sys_prompt: str,
    prompt_con_contexto: str,
    uploaded_urls: list,
    generated_urls: list,
    raw_documents: list = None,
    session_id: str | None = None,
):
    # Cargar keys
    load_ai_keys(db)

    # Determinar proveedor y modelo
    tenant = db.query(Tenant).filter(Tenant.id_tenant == user_db.id_tenant).first()
    if tenant:
        from backend.trial_policy import ensure_ai_usage_allowed
        ensure_ai_usage_allowed(db, tenant)
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
            if not tenant or not tenant.plan or not tenant.plan.permite_iot:
                return "Acceso a IoT no habilitado para este tenant."
            return loop.run_until_complete(iot_service.obtener_estado_dispositivo(**args))
        elif fn_name == "activar_dispositivo":
            if not tenant or not tenant.plan or not tenant.plan.permite_iot:
                return "Acceso a IoT no habilitado para este tenant."
            return loop.run_until_complete(iot_service.activar_dispositivo(**args))
        elif fn_name == "enviar_mensaje_mqtt":
            if not tenant or not tenant.plan or not tenant.plan.permite_iot:
                return "Acceso a IoT no habilitado para este tenant."
            return iot_service.publicar_mensaje_mqtt(**args)
        elif fn_name == "generar_documento":
            import base64
            import urllib.parse
            try:
                contenido = args.get("contenido", "")
                formato = args.get("formato", "txt").lower()
                titulo = args.get("titulo", "Documento")
                
                if formato == "pdf":
                    import io
                    import re
                    from reportlab.lib.pagesizes import letter
                    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
                    from reportlab.lib.styles import getSampleStyleSheet
                    
                    buffer = io.BytesIO()
                    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
                    styles = getSampleStyleSheet()
                    story = []
                    
                    story.append(Paragraph(titulo, styles['Title']))
                    story.append(Spacer(1, 20))
                    
                    for line in contenido.split('\n'):
                        txt = line.strip()
                        if txt:
                            txt = txt.replace("<", "&lt;").replace(">", "&gt;") 
                            txt = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', txt)
                            story.append(Paragraph(txt, styles['Normal']))
                        story.append(Spacer(1, 8))
                            
                    doc.build(story)
                    b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
                    
                    safe_titulo = urllib.parse.quote(f"{titulo}.pdf")
                    data_uri = f"data:application/pdf;name={safe_titulo};base64,{b64}"
                else:
                    mime_type = "text/plain"
                    if formato == "csv": mime_type = "text/csv"
                    elif formato == "md": mime_type = "text/markdown"
                    elif formato == "html": mime_type = "text/html"
                    
                    b64 = base64.b64encode(contenido.encode("utf-8")).decode("utf-8")
                    safe_titulo = urllib.parse.quote(f"{titulo}.{formato}")
                    data_uri = f"data:{mime_type};name={safe_titulo};base64,{b64}"
                    
                generated_urls.append(data_uri)
                return (f"Éxito: Documento '{titulo}' fue generado y emitido. "
                        f"[AVISO DE SISTEMA: Yo como backend ya le envié este archivo físicamente al celular del usuario. NO INTENTES GENERAR NINGÚN ENLACE NI URL FANTASMA ni uses markdown links para descarga. Solo dile charlando que su archivo ha sido enviado].")
            except Exception as e:
                return f"Error al generar documento: {str(e)}"
        elif fn_name == "obtener_estado_red_mikrotik":
            if not tenant or not tenant.plan or not tenant.plan.permite_mikrotik:
                return "Acceso a MikroTik no habilitado para este tenant."
            return obtener_estado_red_mikrotik(**args, id_tenant=user_db.id_tenant)
        elif fn_name == "listar_interfaces_mikrotik":
            if not tenant or not tenant.plan or not tenant.plan.permite_mikrotik:
                return "Acceso a MikroTik no habilitado para este tenant."
            return listar_interfaces_mikrotik(**args, id_tenant=user_db.id_tenant)
        elif fn_name == "ver_clientes_dhcp_mikrotik":
            if not tenant or not tenant.plan or not tenant.plan.permite_mikrotik:
                return "Acceso a MikroTik no habilitado para este tenant."
            return ver_clientes_dhcp_mikrotik(**args, id_tenant=user_db.id_tenant)
        elif fn_name == "comando_mikrotik_avanzado":
            if not tenant or not tenant.plan or not tenant.plan.permite_mikrotik:
                return "Acceso a MikroTik no habilitado para este tenant."
            return comando_mikrotik_avanzado(**args, id_tenant=user_db.id_tenant)
        elif fn_name == "listar_carpetas_documentales":
            from backend.models import KnowledgeFolder
            folders = db.query(KnowledgeFolder).filter(
                KnowledgeFolder.id_tenant == user_db.id_tenant,
            ).order_by(KnowledgeFolder.created_at.asc()).all()
            if not folders:
                return "No hay proyectos ni carpetas documentales aún."
            return "\n".join(
                f"- {folder.nombre} | id={folder.id_folder} | parent_id={folder.parent_id or 'raíz'}"
                for folder in folders
            )
        elif fn_name == "crear_carpeta_documental":
            from backend.models import KnowledgeFolder
            name = str(args.get("nombre", "")).strip()
            parent_id = args.get("parent_id") or None
            if not name:
                return "Error: el nombre de la carpeta es obligatorio."
            if len(name) > 255:
                return "Error: el nombre de la carpeta supera 255 caracteres."
            if parent_id:
                parent = db.query(KnowledgeFolder).filter(
                    KnowledgeFolder.id_folder == parent_id,
                    KnowledgeFolder.id_tenant == user_db.id_tenant,
                ).first()
                if not parent:
                    return "Error: la carpeta padre no existe o no pertenece a tu organización."
            existing = db.query(KnowledgeFolder).filter(
                KnowledgeFolder.id_tenant == user_db.id_tenant,
                KnowledgeFolder.parent_id == parent_id,
                KnowledgeFolder.nombre == name,
            ).first()
            if existing:
                return f"La carpeta ya existe: id={existing.id_folder}."
            folder = KnowledgeFolder(id_tenant=user_db.id_tenant, nombre=name, parent_id=parent_id)
            db.add(folder)
            db.commit()
            return f"Carpeta creada: {folder.nombre} (id={folder.id_folder})."
        elif fn_name == "mover_documento_a_carpeta":
            from backend.models import KnowledgeDocument, KnowledgeFolder
            document = db.query(KnowledgeDocument).filter(
                KnowledgeDocument.id_document == args.get("document_id"),
                KnowledgeDocument.id_tenant == user_db.id_tenant,
            ).first()
            folder = db.query(KnowledgeFolder).filter(
                KnowledgeFolder.id_folder == args.get("folder_id"),
                KnowledgeFolder.id_tenant == user_db.id_tenant,
            ).first()
            if not document or not folder:
                return "Error: documento o carpeta no encontrado en tu organización."
            document.id_folder = folder.id_folder
            db.commit()
            return f"Documento '{document.nombre}' movido a '{folder.nombre}'."
        elif fn_name == "seleccionar_carpeta_documental":
            if not session_id:
                return "Error: esta conversación no tiene una sesión documental seleccionable."
            from backend.models import ChatSession
            from backend.knowledge_service import folder_scope_ids
            folder_id = args.get("folder_id") or None
            if folder_id:
                folder_scope_ids(db, user_db.id_tenant, folder_id)
            session = db.query(ChatSession).filter(
                ChatSession.id_session == session_id,
                ChatSession.id_usuario == user_db.id_usuario,
            ).first()
            if not session:
                return "Error: sesión no encontrada."
            session.active_knowledge_folder_id = folder_id
            db.commit()
            return "Alcance documental actualizado a toda la biblioteca." if not folder_id else f"Proyecto/carpeta activo seleccionado: {folder_id}."
        elif fn_name == "almacenar_conocimiento":
            from backend.models import KnowledgeDocument, DocumentChunk, KnowledgeFolder
            nombre_doc = args.get("nombre_documento", "Documento sin título")
            if not raw_documents:
                return "Error: No se encontró ningún archivo subido en este mensaje para almacenar."
            
            texto_completo = "\n\n".join([d['text'] for d in raw_documents if d['text']])
            if not texto_completo.strip() or texto_completo.startswith("[Error"):
                return "Error: El archivo subido no contenía texto extraíble."

            try:
                # Si la conversación ya tiene un proyecto activo, el documento
                # queda allí; de lo contrario se conserva la carpeta de chat.
                from backend.models import ChatSession
                active_folder_id = None
                if session_id:
                    session = db.query(ChatSession).filter(
                        ChatSession.id_session == session_id,
                        ChatSession.id_usuario == user_db.id_usuario,
                    ).first()
                    active_folder_id = session.active_knowledge_folder_id if session else None
                carpeta_chat = db.query(KnowledgeFolder).filter(
                    KnowledgeFolder.id_tenant == user_db.id_tenant,
                    KnowledgeFolder.id_folder == active_folder_id,
                ).first() if active_folder_id else None
                if not carpeta_chat:
                    carpeta_chat = db.query(KnowledgeFolder).filter(
                        KnowledgeFolder.id_tenant == user_db.id_tenant,
                        KnowledgeFolder.nombre == "Subidos por Chat",
                        KnowledgeFolder.parent_id.is_(None),
                    ).first()
                
                if not carpeta_chat:
                    carpeta_chat = KnowledgeFolder(id_tenant=user_db.id_tenant, nombre="Subidos por Chat")
                    db.add(carpeta_chat)
                    db.commit()
                    db.refresh(carpeta_chat)

                nuevo_doc = KnowledgeDocument(
                    id_tenant=user_db.id_tenant,
                    id_usuario=user_db.id_usuario,
                    id_folder=carpeta_chat.id_folder,
                    nombre=nombre_doc,
                    mime_type="text/plain",
                    byte_size=len(texto_completo.encode("utf-8")),
                    content_sha256=hashlib.sha256(texto_completo.encode("utf-8")).hexdigest(),
                    source_channel="chat",
                    status="processing",
                )
                db.add(nuevo_doc)
                db.commit()
                db.refresh(nuevo_doc)
                
                import textwrap
                partes = textwrap.wrap(texto_completo, width=1000, replace_whitespace=False)
                
                from litellm import embedding
                try:
                    emb_model = "gemini/text-embedding-004" if ai_provider.lower() == "gemini" else "text-embedding-3-small"
                    emb_res = embedding(model=emb_model, input=partes, **({} if ai_provider.lower() == "gemini" else {"dimensions": 768}))
                except Exception as e:
                    nuevo_doc.status, nuevo_doc.error_message = "failed", str(e)[:2000]
                    db.commit()
                    return f"Error al generar vector de embeddings: {str(e)}"
                for idx, (parte, item) in enumerate(zip(partes, emb_res.data)):
                    vector = item['embedding'] if isinstance(item, dict) else item.embedding
                    chk = DocumentChunk(
                        id_document=nuevo_doc.id_document,
                        chunk_index=idx,
                        texto=parte,
                        embedding=vector
                    )
                    db.add(chk)
                
                nuevo_doc.status = "ready"
                nuevo_doc.chunk_count = len(partes)
                nuevo_doc.indexed_at = func.now()
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
                db.rollback()
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
            AIUsageStats.proveedor == ai_provider,
            func.date(AIUsageStats.fecha_registro) == func.current_date(),
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
        try:
            db.commit()
        except:
            db.rollback()

    return respuesta_jarvis, total_tokens


