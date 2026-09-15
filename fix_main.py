with open('backend/main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# First, modify prompt_con_contexto
routers_injection = """
        # --- MikroTik Context Injection ---
        from backend.models import Usuario, MikrotikRouter
        user_db = db.query(Usuario).filter(Usuario.id_usuario == usuario["id_usuario"]).first()
        if user_db:
            routers = db.query(MikrotikRouter).filter(MikrotikRouter.id_tenant == user_db.id_tenant).all()
            if routers:
                routers_str = "\\n".join([f"- ID: {r.id_router} | Nombre: {r.nombre} | IP: {r.ip_address}" for r in routers])
                prompt_con_contexto += f"\\n\\n=== ROUTERS MIKROTIK DISPONIBLES ===\\n{routers_str}\\nPara comandos de red, usa el ID del router en las herramientas MikroTik."
        # ----------------------------------
"""
content = content.replace("contents = [prompt_con_contexto] + gemini_parts", routers_injection + "\n        contents = [prompt_con_contexto] + gemini_parts")

# Next, tool invocation loop
function_call_injection = """
                from backend.mikrotik_tools import obtener_estado_red_mikrotik, listar_interfaces_mikrotik, ver_clientes_dhcp_mikrotik, comando_mikrotik_avanzado
                
                args = {}
                if "args" in function_call:
                    args = dict(function_call.args)
                elif hasattr(function_call, "args"):
                    args = dict(function_call.args)

                fn_name = function_call.name
                res = "Herramienta no encontrada"
                
                if fn_name == "obtener_estado_dispositivo":
                    res = obtener_estado_dispositivo(**args)
                elif fn_name == "activar_dispositivo":
                    res = activar_dispositivo(**args)
                elif fn_name == "enviar_mensaje_mqtt":
                    res = enviar_mensaje_mqtt(**args)
                elif fn_name == "generar_documento":
                    res = generar_documento(**args)
                elif fn_name == "obtener_estado_red_mikrotik":
                    res = obtener_estado_red_mikrotik(**args)
                elif fn_name == "listar_interfaces_mikrotik":
                    res = listar_interfaces_mikrotik(**args)
                elif fn_name == "ver_clientes_dhcp_mikrotik":
                    res = ver_clientes_dhcp_mikrotik(**args)
                elif fn_name == "comando_mikrotik_avanzado":
                    res = comando_mikrotik_avanzado(**args)

                responses.append(types.Part.from_function_response(name=fn_name, response={"result": res}))
"""

# Let's replace the whole `if gr.function_calls:` block inside `enviar_mensaje_chat`
import re
content = re.sub(r'for function_call in gr\.function_calls:.*?responses\.append\(types\.Part\.from_function_response\(name=fn_name, response=\{"result": res\}\)\)', function_call_injection.strip(), content, flags=re.DOTALL)

with open('backend/main.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Injected tool execution and context")
