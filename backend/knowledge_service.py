"""Biblioteca documental multi-canal: extracción, indexación y recuperación."""
from __future__ import annotations

import csv
import hashlib
import io
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.models import DocumentChunk, KnowledgeDocument, KnowledgeFolder, KnowledgeIngestionJob, KnowledgeRetrievalAudit, Tenant

CHUNK_SIZE = 1000
KNOWLEDGE_SUFFIXES = {".pdf", ".txt", ".md", ".csv", ".docx", ".xlsx"}


def storage_is_configured() -> bool:
    return bool(os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_SERVICE_ROLE_KEY"))


def document_quota_snapshot(db: Session, tenant_id: int) -> dict[str, int]:
    tenant = db.query(Tenant).filter_by(id_tenant=tenant_id).first()
    if not tenant or not tenant.plan:
        raise HTTPException(status_code=404, detail="No se encontró el plan de la organización.")
    active_documents = db.query(func.count(KnowledgeDocument.id_document)).filter(
        KnowledgeDocument.id_tenant == tenant_id,
        KnowledgeDocument.status != "superseded",
    ).scalar() or 0
    storage_used = db.query(func.coalesce(func.sum(KnowledgeDocument.byte_size), 0)).filter(
        KnowledgeDocument.id_tenant == tenant_id,
        KnowledgeDocument.storage_path.isnot(None),
    ).scalar() or 0
    return {
        "documents_used": int(active_documents), "documents_limit": int(tenant.plan.max_documentos),
        "storage_used_bytes": int(storage_used), "storage_limit_bytes": int(tenant.plan.almacenamiento_bytes),
        "max_upload_bytes": int(tenant.plan.max_upload_bytes),
    }


def enforce_document_quota(db: Session, tenant_id: int, incoming_bytes: int, replaces_document_id: str | None = None) -> dict[str, int]:
    quota = document_quota_snapshot(db, tenant_id)
    if replaces_document_id:
        previous = db.query(KnowledgeDocument).filter_by(id_document=replaces_document_id, id_tenant=tenant_id).first()
        if previous:
            # La versión saliente deja de contar para la cuota lógica cuando la
            # nueva quede lista, aunque Storage la conserve transitoriamente.
            quota["documents_used"] = max(0, quota["documents_used"] - 1)
            quota["storage_used_bytes"] = max(0, quota["storage_used_bytes"] - int(previous.byte_size or 0))
    if incoming_bytes > quota["max_upload_bytes"]:
        raise HTTPException(status_code=413, detail="El archivo excede el límite de carga de tu plan.")
    if quota["documents_used"] >= quota["documents_limit"]:
        raise HTTPException(status_code=403, detail="Tu plan alcanzó el límite de documentos activos.")
    if quota["storage_used_bytes"] + incoming_bytes > quota["storage_limit_bytes"]:
        raise HTTPException(status_code=403, detail="Tu plan alcanzó el límite de almacenamiento documental.")
    return quota


def _upload_original(*, tenant_id: int, document_id: str, filename: str, content: bytes, mime_type: str | None) -> str | None:
    """Guarda el original en un bucket privado si Storage está configurado."""
    url, key = os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not (url and key):
        return None
    from supabase import create_client
    path = f"tenant/{tenant_id}/knowledge/{document_id}/{filename}"
    bucket = os.getenv("SUPABASE_KNOWLEDGE_BUCKET", "knowledge-originals")
    try:
        create_client(url, key).storage.from_(bucket).upload(
            path, content, {"content-type": mime_type or "application/octet-stream", "upsert": "false"},
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail="No fue posible conservar el archivo original de forma segura.") from exc
    return path


def _download_original(storage_path: str) -> bytes:
    if not storage_is_configured():
        raise RuntimeError("Supabase Storage no está configurado para el worker.")
    from supabase import create_client
    bucket = os.getenv("SUPABASE_KNOWLEDGE_BUCKET", "knowledge-originals")
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"]).storage.from_(bucket).download(storage_path)


def create_download_url(storage_path: str, expires_in: int = 300) -> str:
    """Genera una URL firmada corta; el path interno nunca se expone al cliente."""
    if not storage_is_configured():
        raise RuntimeError("El almacenamiento privado no está configurado.")
    from supabase import create_client
    bucket = os.getenv("SUPABASE_KNOWLEDGE_BUCKET", "knowledge-originals")
    response = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"]).storage.from_(bucket).create_signed_url(storage_path, expires_in)
    url = response.get("signedURL") or response.get("signedUrl")
    if not url:
        raise RuntimeError("Storage no devolvió una URL firmada.")
    return url


def delete_original(storage_path: str) -> None:
    """Elimina el objeto privado al borrar definitivamente un documento."""
    if not storage_is_configured():
        return
    from supabase import create_client
    bucket = os.getenv("SUPABASE_KNOWLEDGE_BUCKET", "knowledge-originals")
    create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"]).storage.from_(bucket).remove([storage_path])


def _supersede_previous_document(db: Session, document: KnowledgeDocument) -> None:
    """Retira el original de una versión anterior sólo después de indexar la nueva."""
    if not document.replaces_document_id:
        return
    previous = db.query(KnowledgeDocument).filter_by(
        id_document=document.replaces_document_id, id_tenant=document.id_tenant,
    ).first()
    if not previous:
        return
    previous.status = "superseded"
    if previous.storage_path:
        try:
            delete_original(previous.storage_path)
            previous.storage_path = None
        except Exception:
            # La versión nueva ya está lista. Mantener el objeto anterior es más
            # seguro que revertir la indexación por una limpieza no esencial.
            pass


def chunk_text(text: str) -> list[str]:
    """Fragmenta respetando párrafos; el contenido nunca se interpreta como instrucciones."""
    paragraphs = [part.strip() for part in text.split("\n\n") if part.strip()] or [text.strip()]
    chunks, current = [], ""
    for paragraph in paragraphs:
        while len(paragraph) > CHUNK_SIZE:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(paragraph[:CHUNK_SIZE])
            paragraph = paragraph[CHUNK_SIZE:]
        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if len(candidate) > CHUNK_SIZE and current:
            chunks.append(current)
            current = paragraph
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def extract_text(filename: str, content: bytes) -> tuple[str, list[dict[str, Any]]]:
    """Extrae texto de formatos empresariales preservando página, hoja o sección."""
    suffix = Path(filename).suffix.lower()
    if suffix not in KNOWLEDGE_SUFFIXES:
        raise HTTPException(status_code=400, detail=f"Formato no soportado para conocimiento: {filename}")
    if suffix == ".pdf":
        import fitz
        pdf = fitz.open(stream=io.BytesIO(content), filetype="pdf")
        pages = [{"page": index + 1, "text": page.get_text().strip()} for index, page in enumerate(pdf)]
        pdf.close()
        return "\n\n".join(f"[Página {p['page']}]\n{p['text']}" for p in pages if p["text"]), [{"page": p["page"]} for p in pages]
    if suffix == ".docx":
        from docx import Document
        document = Document(io.BytesIO(content))
        parts = [p.text.strip() for p in document.paragraphs if p.text.strip()]
        for number, table in enumerate(document.tables, start=1):
            rows = [" | ".join(cell.text.strip() for cell in row.cells) for row in table.rows]
            parts.append(f"[Tabla {number}]\n" + "\n".join(row for row in rows if row.strip()))
        return "\n\n".join(parts), [{"section": "document"}]
    if suffix == ".xlsx":
        from openpyxl import load_workbook
        workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        parts, provenance = [], []
        for sheet in workbook.worksheets:
            rows = []
            for row_number, row in enumerate(sheet.iter_rows(values_only=True), start=1):
                values = ["" if value is None else str(value) for value in row]
                if any(value.strip() for value in values):
                    rows.append(f"Fila {row_number}: " + " | ".join(values))
            if rows:
                parts.append(f"[Hoja: {sheet.title}]\n" + "\n".join(rows))
                provenance.append({"sheet": sheet.title})
        workbook.close()
        return "\n\n".join(parts), provenance
    if suffix == ".csv":
        decoded = content.decode("utf-8-sig", errors="replace")
        try:
            dialect = csv.Sniffer().sniff(decoded[:4096], delimiters=",;\t|")
        except csv.Error:
            dialect = csv.excel
        rows = [f"Fila {index}: " + " | ".join(row) for index, row in enumerate(csv.reader(io.StringIO(decoded), dialect), start=1)]
        return "\n".join(rows), [{"section": "csv"}]
    return content.decode("utf-8-sig", errors="replace"), [{"section": "text"}]


def chunks_with_provenance(filename: str, content: bytes) -> list[tuple[str, dict[str, Any]]]:
    """Genera fragmentos sin perder la página u hoja exacta que los originó."""
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        import fitz
        pdf = fitz.open(stream=io.BytesIO(content), filetype="pdf")
        result = []
        for index, page in enumerate(pdf, start=1):
            page_text = page.get_text().strip()
            result.extend((chunk, {"page": index}) for chunk in chunk_text(page_text) if chunk.strip())
        pdf.close()
        return result
    text, provenance = extract_text(filename, content)
    if suffix == ".xlsx":
        result = []
        for block in [part for part in text.split("\n\n") if part.strip()]:
            match = re.match(r"\[Hoja: (.+?)\]", block)
            metadata = {"sheet": match.group(1)} if match else {"section": "workbook"}
            result.extend((chunk, metadata) for chunk in chunk_text(block) if chunk.strip())
        return result
    metadata = provenance[0] if provenance else {}
    return [(chunk, metadata) for chunk in chunk_text(text) if chunk.strip()]


async def ingest_document(
    db: Session, *, tenant_id: int, user_id: int | None, filename: str, content: bytes,
    mime_type: str | None, source_channel: str, folder_name: str | None = None,
    version: int = 1, replaces_document_id: str | None = None,
) -> KnowledgeDocument:
    """Indexa bytes procedentes de web o Telegram en una única biblioteca por tenant."""
    filename = Path(filename).name
    enforce_document_quota(db, tenant_id, len(content), replaces_document_id)
    text, provenance = extract_text(filename, content)
    if not text.strip():
        raise HTTPException(status_code=422, detail=f"{filename} no contiene texto extraíble.")
    folder = None
    if folder_name:
        folder = db.query(KnowledgeFolder).filter_by(id_tenant=tenant_id, nombre=folder_name).first()
        if not folder:
            folder = KnowledgeFolder(id_tenant=tenant_id, nombre=folder_name)
            db.add(folder)
            db.flush()
    document = KnowledgeDocument(
        id_tenant=tenant_id, id_usuario=user_id, id_folder=folder.id_folder if folder else None,
        nombre=filename, mime_type=mime_type, source_channel=source_channel,
        content_sha256=hashlib.sha256(content).hexdigest(), status="processing",
        version=version, replaces_document_id=replaces_document_id, byte_size=len(content),
    )
    db.add(document)
    db.flush()
    try:
        document.storage_path = _upload_original(
            tenant_id=tenant_id, document_id=document.id_document, filename=filename,
            content=content, mime_type=mime_type,
        )
        tenant = db.query(Tenant).filter_by(id_tenant=tenant_id).first()
        provider = tenant.ai_provider if tenant else "gemini"
        model = "gemini/text-embedding-004" if provider.lower() == "gemini" else "text-embedding-3-small"
        kwargs = {} if provider.lower() == "gemini" else {"dimensions": 768}
        from backend.ai_service import load_ai_keys
        from litellm import aembedding
        load_ai_keys(db)
        chunks = chunks_with_provenance(filename, content)
        for index, (chunk, metadata) in enumerate(chunks):
            embedding_result = await aembedding(model=model, input=[chunk], **kwargs)
            vector = embedding_result.data[0]["embedding"] if isinstance(embedding_result.data[0], dict) else embedding_result.data[0].embedding
            db.add(DocumentChunk(id_document=document.id_document, chunk_index=index, texto=chunk, embedding=vector, metadata_json=metadata))
        document.chunk_count, document.status = len(chunks), "ready"
        document.indexed_at = datetime.now(timezone.utc)
        _supersede_previous_document(db, document)
        db.commit()
        db.refresh(document)
        return document
    except Exception as exc:
        db.rollback()
        # No se deja un documento como "ready" si su indexación falló.
        document.status, document.error_message = "failed", str(exc)[:2000]
        db.add(document)
        db.commit()
        raise HTTPException(status_code=502, detail=f"No fue posible indexar {filename}.") from exc


def queue_document(
    db: Session, *, tenant_id: int, user_id: int | None, filename: str, content: bytes,
    mime_type: str | None, source_channel: str, folder_name: str | None = None,
    version: int = 1, replaces_document_id: str | None = None,
) -> KnowledgeDocument:
    """Conserva el original y crea un trabajo durable; responde sin esperar embeddings."""
    if not storage_is_configured():
        raise RuntimeError("La cola documental requiere Supabase Storage configurado.")
    filename = Path(filename).name
    enforce_document_quota(db, tenant_id, len(content), replaces_document_id)
    folder = None
    if folder_name:
        folder = db.query(KnowledgeFolder).filter_by(id_tenant=tenant_id, nombre=folder_name).first()
        if not folder:
            folder = KnowledgeFolder(id_tenant=tenant_id, nombre=folder_name)
            db.add(folder)
            db.flush()
    document = KnowledgeDocument(
        id_tenant=tenant_id, id_usuario=user_id, id_folder=folder.id_folder if folder else None,
        nombre=filename, mime_type=mime_type, source_channel=source_channel,
        content_sha256=hashlib.sha256(content).hexdigest(), status="queued",
        version=version, replaces_document_id=replaces_document_id, byte_size=len(content),
    )
    db.add(document)
    db.flush()
    try:
        document.storage_path = _upload_original(
            tenant_id=tenant_id, document_id=document.id_document, filename=filename,
            content=content, mime_type=mime_type,
        )
        db.add(KnowledgeIngestionJob(id_document=document.id_document, status="queued"))
        db.commit()
        db.refresh(document)
        return document
    except Exception:
        db.rollback()
        raise


async def _index_existing_document(db: Session, document: KnowledgeDocument, content: bytes) -> None:
    chunks = chunks_with_provenance(document.nombre, content)
    if not chunks:
        raise RuntimeError("El documento no contiene texto extraíble.")
    tenant = db.query(Tenant).filter_by(id_tenant=document.id_tenant).first()
    provider = tenant.ai_provider if tenant else "gemini"
    model = "gemini/text-embedding-004" if provider.lower() == "gemini" else "text-embedding-3-small"
    kwargs = {} if provider.lower() == "gemini" else {"dimensions": 768}
    from backend.ai_service import load_ai_keys
    from litellm import aembedding
    load_ai_keys(db)
    db.query(DocumentChunk).filter_by(id_document=document.id_document).delete(synchronize_session=False)
    for index, (chunk, metadata) in enumerate(chunks):
        result = await aembedding(model=model, input=[chunk], **kwargs)
        vector = result.data[0]["embedding"] if isinstance(result.data[0], dict) else result.data[0].embedding
        db.add(DocumentChunk(id_document=document.id_document, chunk_index=index, texto=chunk, embedding=vector, metadata_json=metadata))
    document.chunk_count = len(chunks)
    document.status = "ready"
    document.error_message = None
    document.indexed_at = datetime.now(timezone.utc)
    _supersede_previous_document(db, document)


async def process_next_job(db: Session) -> bool:
    """Toma un trabajo con bloqueo de fila para permitir varios workers sin duplicar."""
    job = db.query(KnowledgeIngestionJob).filter_by(status="queued").order_by(
        KnowledgeIngestionJob.created_at.asc()
    ).with_for_update(skip_locked=True).first()
    if not job:
        return False
    document = job.document
    job_id, document_id = job.id_job, document.id_document
    job.status, job.attempts, job.started_at = "processing", job.attempts + 1, datetime.now(timezone.utc)
    document.status = "processing"
    db.commit()
    try:
        if not document.storage_path:
            raise RuntimeError("El documento no tiene original en Storage.")
        await _index_existing_document(db, document, _download_original(document.storage_path))
        job.status, job.finished_at, job.error_message = "completed", datetime.now(timezone.utc), None
        db.commit()
    except Exception as exc:
        db.rollback()
        job = db.query(KnowledgeIngestionJob).filter_by(id_job=job_id).first()
        document = db.query(KnowledgeDocument).filter_by(id_document=document_id).first()
        terminal = job.attempts >= job.max_attempts
        job.status, job.error_message = ("failed" if terminal else "queued"), str(exc)[:2000]
        if terminal:
            document.status, document.error_message = "failed", job.error_message
        else:
            document.status = "queued"
        db.commit()
    return True


async def submit_document(**kwargs) -> KnowledgeDocument:
    """En producción encola; en desarrollo sin Storage conserva compatibilidad síncrona."""
    if storage_is_configured():
        return queue_document(**kwargs)
    return await ingest_document(**kwargs)


def _lexical_overlap(query: str, text: str) -> float:
    terms = {term for term in re.findall(r"\w+", query.lower(), flags=re.UNICODE) if len(term) >= 3}
    if not terms:
        return 0.0
    text_terms = set(re.findall(r"\w+", text.lower(), flags=re.UNICODE))
    return len(terms & text_terms) / len(terms)


async def retrieve_knowledge(
    db: Session, *, tenant_id: int, query: str, limit: int = 4,
    user_id: int | None = None, channel: str = "web",
) -> list[dict[str, Any]]:
    """Recuperación vectorial con reranking léxico, diversidad y auditoría privada."""
    tenant = db.query(Tenant).filter_by(id_tenant=tenant_id).first()
    provider = tenant.ai_provider if tenant else "gemini"
    model = "gemini/text-embedding-004" if provider.lower() == "gemini" else "text-embedding-3-small"
    kwargs = {} if provider.lower() == "gemini" else {"dimensions": 768}
    from backend.ai_service import load_ai_keys
    from litellm import aembedding
    load_ai_keys(db)
    result = await aembedding(model=model, input=[query], **kwargs)
    vector = result.data[0]["embedding"] if isinstance(result.data[0], dict) else result.data[0].embedding
    distance = DocumentChunk.embedding.cosine_distance(vector).label("distance")
    candidates = db.query(DocumentChunk, KnowledgeDocument, distance).join(KnowledgeDocument).filter(
        KnowledgeDocument.id_tenant == tenant_id, KnowledgeDocument.status == "ready",
    ).order_by(distance).limit(max(limit * 3, 12)).all()

    ranked = []
    for chunk, doc, raw_distance in candidates:
        semantic = max(0.0, 1.0 - min(float(raw_distance or 1.0), 2.0) / 2.0)
        score = round((semantic * 0.8) + (_lexical_overlap(query, chunk.texto or "") * 0.2), 4)
        ranked.append((score, chunk, doc))
    ranked.sort(key=lambda item: item[0], reverse=True)
    # Evita que un solo documento monopolice todo el contexto del modelo.
    selected, per_document = [], {}
    for score, chunk, doc in ranked:
        if per_document.get(doc.id_document, 0) >= 2:
            continue
        selected.append((score, chunk, doc))
        per_document[doc.id_document] = per_document.get(doc.id_document, 0) + 1
        if len(selected) >= limit:
            break

    db.add(KnowledgeRetrievalAudit(
        id_tenant=tenant_id, id_usuario=user_id, channel=channel,
        query_sha256=hashlib.sha256(query.encode("utf-8")).hexdigest(),
        result_document_ids=[doc.id_document for _, _, doc in selected],
        result_chunk_ids=[chunk.id for _, chunk, _ in selected],
        result_scores=[score for score, _, _ in selected],
    ))
    return [{"document_id": doc.id_document, "document_name": doc.nombre, "text": chunk.texto,
             "score": score, "citation": {"document": doc.nombre, "document_id": doc.id_document, **(chunk.metadata_json or {})}}
            for score, chunk, doc in selected]
