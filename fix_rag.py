with open('backend/main.py', 'r', encoding='utf-8') as f:
    content = f.read()

import re

# 1. Import DocumentChunk
if "DocumentChunk" not in content:
    content = content.replace("from backend.models import ChatSession, ChatMessage, Base", "from backend.models import ChatSession, ChatMessage, DocumentChunk, Base")

# 2. Logic for Focused Documents (Retrieval)
old_focused = """    focused_knowledge = ""
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
                            pass"""

new_focused = """    focused_knowledge = ""
    if focused_ids_list:
        try:
            # 1. Embed user query
            _gc = get_gemini_client()
            q_emb_resp = _gc.models.embed_content(
                model="text-embedding-004",
                contents=mensaje if mensaje else "Resumen del documento"
            )
            q_vec = q_emb_resp.embeddings[0].values
            
            # 2. Retrieve top chunks
            chunks = db.query(DocumentChunk).filter(
                DocumentChunk.id_mensaje.in_(focused_ids_list)
            ).order_by(
                DocumentChunk.embedding.cosine_distance(q_vec)
            ).limit(4).all()
            
            if chunks:
                focused_knowledge = "\\n".join([f"- {c.texto}" for c in chunks])
        except Exception as e:
            print(f"Error en RAG retrieval: {e}")"""

if 'DocumentChunk.embedding.cosine_distance' not in content:
    content = content.replace(old_focused, new_focused)

# 3. Logic for chunking new documents
old_save = """    msg_user = ChatMessage(id_session=session_id, rol="user", contenido=contenido_usuario, file_urls=uploaded_urls)
    db.add(msg_user)"""

new_save = """    msg_user = ChatMessage(id_session=session_id, rol="user", contenido=contenido_usuario, file_urls=uploaded_urls)
    db.add(msg_user)
    db.flush()

    if doc_context.strip():
        try:
            # Simple chunking
            chunk_size = 1000
            text_chunks = [doc_context[i:i+chunk_size] for i in range(0, len(doc_context), chunk_size)]
            
            _gc = get_gemini_client()
            for i, chunk_text in enumerate(text_chunks):
                emb_resp = _gc.models.embed_content(
                    model="text-embedding-004",
                    contents=chunk_text
                )
                vec = emb_resp.embeddings[0].values
                db.add(DocumentChunk(
                    id_mensaje=msg_user.id_mensaje,
                    chunk_index=i,
                    texto=chunk_text,
                    embedding=vec
                ))
        except Exception as e:
            print(f"Error generando embeddings: {e}")"""

if "DocumentChunk(" not in content:
    content = content.replace(old_save, new_save)


with open('backend/main.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated backend/main.py with RAG logic")
