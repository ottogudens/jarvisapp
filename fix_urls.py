with open('backend/main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Introduce generated_urls
content = content.replace("uploaded_urls: list = []\n    gemini_parts: list = []", "uploaded_urls: list = []\n    generated_urls: list = []\n    gemini_parts: list = []")

# Update generar_documento to append to generated_urls
content = content.replace("uploaded_urls.append(public_url)", "generated_urls.append(public_url)")

# Pass to msg_jarvis
old_jarvis = 'msg_jarvis = ChatMessage(id_session=session_id, rol="jarvis", contenido=respuesta_jarvis, file_urls=[])'
new_jarvis = 'msg_jarvis = ChatMessage(id_session=session_id, rol="jarvis", contenido=respuesta_jarvis, file_urls=generated_urls)'
content = content.replace(old_jarvis, new_jarvis)

with open('backend/main.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated message generation logic.")
