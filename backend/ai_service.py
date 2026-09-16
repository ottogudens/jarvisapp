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
                }
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
                }
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
                "properties": {"id_router": {"type": "integer"}}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "comando_mikrotik_avanzado",
            "description": "Ejecuta un comando raw específico en la API del router (ej: /ip/address/print).",
            "parameters": {
                "type": "object",
                "properties": {
                    "comando": {"type": "string", "description": "Comando API (ej. /ip/route/print)"},
                    "id_router": {"type": "integer"}
                },
                "required": ["comando"]
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
    prompt_con_contexto: str,
    uploaded_urls: list,
    generated_urls: list
):
    # Cargar keys
    load_ai_keys(db)

    # Determinar proveedor y modelo
    tenant = db.query(Tenant).filter(Tenant.id_tenant == user_db.id_tenant).first()
    ai_provider = tenant.ai_provider if tenant else "gemini"
    ai_model = tenant.ai_model if tenant else "gemini-3.6-flash"
    
    # Adaptar prefijos de modelo para litellm
    model_name = ai_model
    if ai_provider.lower() == "gemini" and not model_name.startswith("gemini/"):
        model_name = f"gemini/{model_name}"
    elif ai_provider.lower() == "deepseek" and not model_name.startswith("deepseek/"):
        model_name = f"deepseek/{model_name}"

    # Construir mensajes
    content_list = [{"type": "text", "text": prompt_con_contexto}]
    for url in uploaded_urls:
        if url.startswith("data:image/"):
            content_list.append({"type": "image_url", "image_url": {"url": url}})
    
    messages = [{"role": "user", "content": content_list}]

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
            import os, uuid
            from supabase import create_client, Client
            try:
                url = os.getenv("SUPABASE_URL")
                key = os.getenv("SUPABASE_KEY")
                if not url or not key: return "Error: Supabase no está configurado."
                supabase: Client = create_client(url, key)
                filename = f"{uuid.uuid4()}.{args.get('formato', 'txt')}"
                path = f"/tmp/{filename}"
                with open(path, "w", encoding="utf-8") as file:
                    file.write(args.get("contenido", ""))
                with open(path, "rb") as file:
                    supabase.storage.from_("jarvis-files").upload(filename, file)
                public_url = supabase.storage.from_("jarvis-files").get_public_url(filename)
                generated_urls.append(public_url)
                return f"Documento '{args.get('titulo')}' generado. URL: {public_url}"
            except Exception as e: return f"Error al generar documento: {str(e)}"
        elif fn_name == "obtener_estado_red_mikrotik":
            return obtener_estado_red_mikrotik(**args)
        elif fn_name == "listar_interfaces_mikrotik":
            return listar_interfaces_mikrotik(**args)
        elif fn_name == "ver_clientes_dhcp_mikrotik":
            return ver_clientes_dhcp_mikrotik(**args)
        elif fn_name == "comando_mikrotik_avanzado":
            return comando_mikrotik_avanzado(**args)
        return "Herramienta desconocida"

    total_tokens = 0
    try:
        response = litellm.completion(
            model=model_name,
            messages=messages,
            tools=LITELLM_TOOLS,
            temperature=0.7
        )
        if response.usage:
            total_tokens += response.usage.total_tokens

        message = response.choices[0].message
        
        # Tool call detectado
        if message.tool_calls:
            messages.append(message) # Agregar el mensaje con el tool call
            
            for tool_call in message.tool_calls:
                fn_name = tool_call.function.name
                args = json.loads(tool_call.function.arguments)
                res = ejecutar_herramienta(fn_name, args)
                
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": fn_name,
                    "content": res
                })
            
            # Segunda llamada para que el modelo responda con el resultado
            response2 = litellm.completion(
                model=model_name,
                messages=messages,
                temperature=0.7
            )
            if response2.usage:
                total_tokens += response2.usage.total_tokens
            
            respuesta_jarvis = response2.choices[0].message.content or "Ejecuté sus órdenes, señor."
        else:
            respuesta_jarvis = message.content or "Entendido."

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
