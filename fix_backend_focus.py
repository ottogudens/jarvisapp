with open('backend/main.py', 'r', encoding='utf-8') as f:
    content = f.read()

import re

# 1. Signature update
old_sig = """    custom_prompt: Optional[str] = Form(None),
    files: List[UploadFile] = File(default=[]),"""
new_sig = """    custom_prompt: Optional[str] = Form(None),
    focused_document_ids: Optional[str] = Form(None),
    files: List[UploadFile] = File(default=[]),"""
content = content.replace(old_sig, new_sig)

# 2. Logic injection before `knowledge_from_history = ""`
old_hist_start = """    mensajes_hist = db.query(ChatMessage).filter(
        ChatMessage.id_session == session_id
    ).order_by(ChatMessage.created_at.asc()).all()

    knowledge_from_history = """"""
new_hist_start = """    mensajes_hist = db.query(ChatMessage).filter(
        ChatMessage.id_session == session_id
    ).order_by(ChatMessage.created_at.asc()).all()

    import json
    focused_ids_list = []
    if focused_document_ids:
        try:
            focused_ids_list = json.loads(focused_document_ids)
            if not isinstance(focused_ids_list, list):
                focused_ids_list = []
        except:
            pass

    focused_knowledge = ""
    if focused_ids_list:
        for hist_msg in mensajes_hist:
            if hist_msg.id_mensaje in focused_ids_list and hist_msg.file_urls:
                for url in (hist_msg.file_urls or []):
                    if "base64," in url and (url.startswith("data:text/") or url.startswith("data:application/pdf")):
                        try:
                            _, b64_part = url.split("base64,", 1)
                            raw = base64.b64decode(b64_part).decode("utf-8", errors="ignore")
                            if raw.strip():
                                focused_knowledge += f"\\n\\n=== DOCUMENTO SELECCIONADO PARA FOCO ({hist_msg.id_mensaje}) ===\\n{raw[:20000]}"
                        except Exception:
                            pass

    knowledge_from_history = ""
"""
content = content.replace(old_hist_start, new_hist_start)

# 3. Exclude focused docs from general history loop and prompt
old_loop = """    for hist_msg in mensajes_hist[-12:]:
        if hist_msg.rol == "user" and hist_msg.file_urls:"""
new_loop = """    for hist_msg in mensajes_hist[-12:]:
        if hist_msg.id_mensaje in focused_ids_list:
            continue
        if hist_msg.rol == "user" and hist_msg.file_urls:"""
content = content.replace(old_loop, new_loop)

# 4. Inject focused_knowledge to prompt
old_prompt = """    if knowledge_from_history:
        prompt_con_contexto += f"[CONOCIMIENTO DE DOCUMENTOS PREVIOS EN ESTA SESIÓN]{knowledge_from_history}\\n\\n"
    if doc_context:"""
new_prompt = """    if focused_knowledge:
        prompt_con_contexto += f"[DOCUMENTOS SELECCIONADOS COMO FOCO PRINCIPAL]\\n(Instrucción: El usuario te pide que te enfoques PRINCIPALMENTE en estos documentos para responder)\\n{focused_knowledge}\\n\\n"
    if knowledge_from_history:
        prompt_con_contexto += f"[CONOCIMIENTO DE DOCUMENTOS PREVIOS EN ESTA SESIÓN]{knowledge_from_history}\\n\\n"
    if doc_context:"""
content = content.replace(old_prompt, new_prompt)


with open('backend/main.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated backend/main.py")
