with open('backend/main.py', 'r', encoding='utf-8') as f:
    content = f.read()

import_statement = "from backend.mikrotik_tools import mikrotik_tools\n\ntools_list = [obtener_estado_dispositivo, activar_dispositivo, enviar_mensaje_mqtt, generar_documento] + mikrotik_tools"

content = content.replace("tools=[obtener_estado_dispositivo, activar_dispositivo, enviar_mensaje_mqtt, generar_documento],", "tools=tools_list,")
content = content.replace("import get_gemini_client", "import get_gemini_client\n" + import_statement)

# Context Injection: We need to inject the routers into the System Instruction.
# Let's find the system_instruction part.
import re
system_instruction_replacement = """
    # Fetch Mikrotik Routers
    from backend.models import MikrotikRouter
    routers = db.query(MikrotikRouter).filter(MikrotikRouter.id_tenant == user.id_tenant).all()
    routers_context = "No hay routers MikroTik configurados."
    if routers:
        routers_context = "Routers MikroTik Disponibles:\\n" + "\\n".join([f"- ID: {r.id_router} | Nombre: {r.nombre} | IP: {r.ip_address}" for r in routers])

    sys_inst_dinamica = f\"\"\"
    Eres J.A.R.V.I.S., el agente de inteligencia artificial de este sistema.
    Perfil del usuario actual: {user.perfil_jarvis}
    Empresa/Organización: {tenant.nombre_organizacion if tenant else 'Desconocida'}
    
    Contexto de Dispositivos de Red:
    {routers_context}
    \"\"\"
"""
# Assuming the sys_inst is dynamically generated in main.py, I will find where it's generated.
