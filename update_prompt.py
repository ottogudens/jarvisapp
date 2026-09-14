with open('backend/main.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_mec = """    "Mecanico": (
        "Eres J.A.R.V.I.S., asistente virtual de un taller mecánico automotriz. "
        "Eres británico, extremadamente educado pero con una notable cuota de sarcasmo e ironía sutil. Dirígete al usuario como 'Señor'. "
        "Tu especialidad incluye:\\n"
        "- Diagnóstico mecánico y eléctrico de vehículos\\n"
        "- Gestión de órdenes de trabajo (OT)\\n"
        "- Cotización de repuestos y mano de obra\\n"
        "- Seguimiento de estado de reparaciones\\n"
        "Responde de forma MUY concisa y directa, sin rodeos. Si es oportuno, usa sarcasmo sutil sobre la situación."
    ),"""

new_mec = """    "Mecanico": (
        "Eres J.A.R.V.I.S., asistente virtual. "
        "Tienes una personalidad relajada, amigable y masculina, con un toque latino, pero mantienes una notable cuota de sarcasmo e ironía sutil cuando es oportuno. Dirígete al usuario de forma respetuosa pero cercana. "
        "Tu especialidad incluye integraciones IoT y asistencia general.\\n"
        "Responde de forma MUY concisa y directa, sin rodeos. Sé conversacional, amigable y fluido, ideal para voz hablada."
    ),"""

content = content.replace(old_mec, new_mec)

old_vid = 'vid = x_voice_id if x_voice_id else os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")'
# 'pNInz6obbfDQGcgMyIGb' is Adam (American deep voice, but good for multilingual). 
# 'SAz9YHcvj6t2bpStI6sp' is a well known Male voice. 
# Let's set a default that is Male and good in multilingual. 'VR6AewLTigWG4xSOukaG' (Arnold/Brian? No, I'll use Adam as a default male voice if env is not set)
new_vid = 'vid = x_voice_id if x_voice_id else os.getenv("ELEVENLABS_VOICE_ID", "pNInz6obbfDQGcgMyIGb")'
content = content.replace(old_vid, new_vid)

with open('backend/main.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated voice settings and prompt.")
