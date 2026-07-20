"""
DocTel document upload and ingestion router.

Endpoints for uploading files, triggering ingestion, retrying failed
ingestions, and streaming ingestion progress via SSE.
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

from app.routers.deps import (
    APIRouter,
    Depends,
    HTTPException,
    Body,
    UploadFile,
    File,
    Form,
    StreamingResponse,
    select,
    delete,
    text,
    get_file_hash,
    enqueue_ingest,
    Document,
    DbDocument,
    Chunk,
    Embedding,
    DocAnalysis,
    SuggestedPrompt,
    User,
    Project,
    ProjectMember,
    AsyncSession,
    get_db,
    get_current_user,
    require_role,
    check_project_access,
    ensure_project_membership,
    _parse_document_id,
    _assert_document_workspace_access,
    settings,
    os,
    uuid,
    datetime,
    asyncio,
    Optional,
    List,
    _metrics,
    UploadResponse,
    UploadedDocument,
)

router = APIRouter(tags=["ingest"])


# ---------------------------------------------------------------------------
# POST /api/upload – multi-file upload with project access
# ---------------------------------------------------------------------------
@router.post("/api/upload", response_model=UploadResponse)
async def upload_documents(
    project_id: int,
    file: Optional[UploadFile] = File(None),
    files: Optional[List[UploadFile]] = File(None),
    title: Optional[str] = Form(None),
    date: Optional[str] = Form(None),
    is_public: bool = Form(False),
    user: User = Depends(require_role(["admin", "analyst"])),
    db: AsyncSession = Depends(get_db)
):
    await check_project_access(project_id, user, db)
    await ensure_project_membership(project_id, user, db, role_in_project="analyst")

    incoming = files or ([] if file is None else [file])
    if not incoming:
        raise HTTPException(status_code=400, detail="No files provided")
    uploaded_docs = []
    for file_item in incoming:
        # Save to uploads dir
        file_path = settings.uploads_dir / f"{project_id}_{file_item.filename}"
        total = 0
        with open(file_path, "wb") as f:
            while True:
                chunk = await file_item.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > 64 * 1024 * 1024:
                    f.close()
                    try:
                        os.remove(file_path)
                    except Exception:
                        pass
                    raise HTTPException(status_code=413, detail="File too large (max 64MB)")
                f.write(chunk)

        sha256 = await get_file_hash(str(file_path))

        # Re-set RLS context; intermediate commits in ensure_project_membership
        # may have cleared the SET LOCAL app.current_user_id setting.
        await db.execute(
            text("SELECT set_config('app.current_user_id', :val, true)"),
            {"val": str(user.id)}
        )

        doc_title = title or Path(file_item.filename).stem
        doc = Document(
            owner_id=user.id,
            created_by=user.id,
            title=doc_title,
            project_id=project_id,
            uploaded_by_user_id=user.id,
            filename=file_item.filename,
            path=str(file_path),
            mime_type=file_item.content_type,
            sha256=sha256,
            is_public=is_public,
            status="uploaded",
            ingest_step="uploaded",
            ingest_percent=0,
            ingest_message="Uploaded",
            detected_type=Path(file_item.filename).suffix.lower().lstrip("."),
            auto_project_confidence=1.0,
            needs_project_review=False,
        )
        doc.doc_type = doc.detected_type
        doc.doc_date = date
        db.add(doc)
        await db.commit()
        job_id = await enqueue_ingest("document_ingest", document_id=doc.id, owner_id=user.id)
        if job_id is None:
            logger.error("[INGEST] Failed to enqueue ingest job for document %s (owner=%s)", doc.id, user.id)

        uploaded_docs.append(UploadedDocument(
            id=f"doc_{doc.id}",
            filename=doc.filename,
            status=doc.status,
            detected_type=doc.detected_type,
            is_public=bool(doc.is_public),
        ))

    return UploadResponse(documents=uploaded_docs)


# ---------------------------------------------------------------------------
# POST /documents – single-file upload with optional project creation
# ---------------------------------------------------------------------------
@router.post("/documents")
async def upload_document_single(
    file: UploadFile = File(...),
    project_id: Optional[int] = Form(None),
    project_name: Optional[str] = Form(None),
    document_type: Optional[str] = Form(None),
    document_date: Optional[str] = Form(None),
    is_public: bool = Form(False),
    user: User = Depends(require_role(["admin", "analyst"])),
    db: AsyncSession = Depends(get_db),
):
    pid = project_id
    if pid is None and project_name:
        proj = Project(name=project_name, owner_user_id=user.id)
        db.add(proj)
        await db.commit()
        pid = proj.id
    if pid is None:
        raise HTTPException(status_code=400, detail="project_id or project_name required")

    await check_project_access(pid, user, db)
    await ensure_project_membership(pid, user, db, role_in_project="admin" if user.role == "admin" else "analyst")

    # Re-set RLS context; intermediate commits in project creation or
    # ensure_project_membership may have cleared the SET LOCAL setting.
    await db.execute(
        text("SELECT set_config('app.current_user_id', :val, true)"),
        {"val": str(user.id)}
    )

    dest = settings.uploads_dir / f"{pid}_{file.filename}"
    total = 0
    with open(dest, "wb") as f:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > 64 * 1024 * 1024:
                f.close()
                try:
                    os.remove(dest)
                except Exception:
                    pass
                raise HTTPException(status_code=413, detail="File too large (max 64MB)")
            f.write(chunk)
    sha256 = await get_file_hash(str(dest))
    doc_title = Path(file.filename).stem
    doc = Document(
        owner_id=user.id,
        created_by=user.id,
        title=doc_title,
        project_id=pid,
        uploaded_by_user_id=user.id,
        filename=file.filename,
        path=str(dest),
        mime_type=file.content_type,
        sha256=sha256,
        is_public=is_public,
        auto_project_confidence=1.0,
        needs_project_review=False,
    )
    doc.doc_type = Path(file.filename).suffix.lower().lstrip(".")
    doc.doc_date = document_date
    doc.status = "uploaded"
    doc.ingest_step = "uploaded"
    doc.ingest_percent = 0
    doc.ingest_message = "Uploaded"
    doc.detected_type = doc.doc_type
    db.add(doc)
    await db.commit()
    _metrics["uploads_total"] += 1
    job_id = await enqueue_ingest("document_ingest", document_id=doc.id, owner_id=user.id)
    if job_id is None:
        logger.error("[INGEST] Failed to enqueue ingest job for document %s (owner=%s)", doc.id, user.id)
    return {"id": f"doc_{doc.id}", "filename": doc.filename, "status": "uploaded", "is_public": is_public, "detected_type": doc.detected_type, "metadata": {
        "project_id": str(pid), "document_type": document_type, "document_date": document_date
    }}


# ---------------------------------------------------------------------------
# POST /api/ingest/retry – cascade-delete chunks/embeddings and re-enqueue
# ---------------------------------------------------------------------------
@router.post("/api/ingest/retry")
async def ingest_retry(payload: dict = Body(...), user: User = Depends(require_role(["admin", "analyst"])), db: AsyncSession = Depends(get_db)):
    doc_int = _parse_document_id(payload.get("document_id", ""))
    result = await db.execute(select(DbDocument).where(DbDocument.id == doc_int))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    await _assert_document_workspace_access(doc, user, db)
    emb_ids_res = await db.execute(select(Chunk.embedding_id).where(Chunk.document_id == doc_int))
    emb_ids = [int(x) for x in emb_ids_res.scalars().all() if x is not None]
    await db.execute(delete(Chunk).where(Chunk.document_id == doc_int))
    if emb_ids:
        await db.execute(delete(Embedding).where(Embedding.id.in_(emb_ids)))
    await db.execute(delete(SuggestedPrompt).where(SuggestedPrompt.document_id == doc_int))
    await db.execute(delete(DocAnalysis).where(DocAnalysis.document_id == doc_int))
    await db.commit()
    try:
        from app.utils.chroma_client import chroma
        chroma.delete_where(str(doc.project_id), {"document_id": doc_int})
    except Exception:
        pass
    doc.status = "uploaded"
    doc.ingest_step = "uploaded"
    doc.ingest_percent = 0
    doc.ingest_message = "Retry queued"
    doc.error_message = ""
    # Reset all ingestion state booleans to avoid stale-state issues
    doc.ingestion_started = False
    doc.ingestion_completed = False
    doc.ingestion_failed = False
    doc.analysis_ready = False
    db.add(doc)
    await db.commit()
    job_id = await enqueue_ingest("document_ingest", document_id=doc.id, owner_id=doc.owner_id)
    if job_id is None:
        logger.error("[INGEST] Failed to enqueue retry job for document %s (owner=%s)", doc.id, doc.owner_id)
    return {"ok": True}


# ---------------------------------------------------------------------------
# POST /api/ingest/{doc_id} – manually trigger ingestion for a doc
# ---------------------------------------------------------------------------
@router.post("/api/ingest/{doc_id}")
async def trigger_ingestion(
    doc_id: uuid.UUID,
    user: User = Depends(require_role(["admin", "analyst"])),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(DbDocument).where(DbDocument.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    await _assert_document_workspace_access(doc, user, db)
    job_id = await enqueue_ingest("document_ingest", document_id=doc_id, owner_id=doc.owner_id)
    if job_id is None:
        logger.error("[INGEST] Failed to trigger ingestion for document %s (owner=%s)", doc_id, doc.owner_id)
    return {"status": "queued"}


# ---------------------------------------------------------------------------
# GET /api/ingest/status – query document ingestion status
# ---------------------------------------------------------------------------
@router.get("/api/ingest/status")
async def ingest_status(document_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    doc_int = _parse_document_id(document_id)
    result = await db.execute(select(DbDocument).where(DbDocument.id == doc_int))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    await _assert_document_workspace_access(doc, user, db)
    if doc.status == "ingesting" and doc.updated_at is not None:
        try:
            dt = doc.updated_at
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=datetime.timezone.utc)
            if (datetime.datetime.now(datetime.timezone.utc) - dt).total_seconds() > 15 * 60:
                doc.status = "failed"
                doc.ingest_step = "failed"
                doc.ingest_message = "Timed out"
                doc.error_message = "Ingestion exceeded timeout window. Please retry."
                doc.ingestion_failed = True
                db.add(doc)
                await db.commit()
        except Exception:
            pass
    ares = await db.execute(select(DocAnalysis.id).where(DocAnalysis.document_id == doc_int))
    if ares.first():
        if doc.status != "completed":
            doc.status = "completed"
            doc.ingest_step = "completed"
            doc.ingest_percent = 100
            doc.ingest_message = "Completed"
            doc.error_message = ""
        doc.analysis_ready = True
        doc.ingestion_started = True
        doc.ingestion_completed = True
        doc.ingestion_failed = False
        db.add(doc)
        await db.commit()
    return {
        "document_id": doc_int,
        "status": doc.status,
        "step": doc.ingest_step,
        "percent": doc.ingest_percent,
        "message": doc.ingest_message,
        "error_message": doc.error_message or None,
        "analysis_ready": bool(getattr(doc, "analysis_ready", False)),
        "ingestion_started": bool(getattr(doc, "ingestion_started", False)),
        "ingestion_completed": bool(getattr(doc, "ingestion_completed", False)),
        "ingestion_failed": bool(getattr(doc, "ingestion_failed", False)),
        "updated_at": doc.updated_at or "",
    }


# ---------------------------------------------------------------------------
# GET /api/ingest/{document_id}/status – alias for ingest_status
# ---------------------------------------------------------------------------
@router.get("/api/ingest/{document_id}/status")
async def ingest_status_alias(document_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await ingest_status(document_id=document_id, user=user, db=db)


# ---------------------------------------------------------------------------
# GET /api/ingest/stream – SSE stream of ingestion progress
# ---------------------------------------------------------------------------
@router.get("/api/ingest/stream")
async def ingest_stream(document_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    doc_int = _parse_document_id(document_id)
    result = await db.execute(select(DbDocument).where(DbDocument.id == doc_int))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    await _assert_document_workspace_access(doc, user, db)

    async def event_gen():
        last = None
        while True:
            res = await db.execute(select(DbDocument).where(DbDocument.id == doc_int))
            row = res.scalar_one_or_none()
            if not row:
                payload = {"status": "failed", "step": "failed", "percent": 0, "message": "Document missing", "updated_at": ""}
                data = json.dumps(payload)
                yield f"data: {data}\n\n"
                return
            try:
                ares = await db.execute(select(DocAnalysis.id).where(DocAnalysis.document_id == doc_int))
                if ares.first():
                    if row.status != "completed":
                        row.status = "completed"
                        row.ingest_step = "completed"
                        row.ingest_percent = 100
                        row.ingest_message = "Completed"
                        row.error_message = ""
                    row.analysis_ready = True
                    row.ingestion_started = True
                    row.ingestion_completed = True
                    row.ingestion_failed = False
                    db.add(row)
                    await db.commit()
            except Exception:
                pass
            payload = {
                "document_id": doc_int,
                "status": row.status,
                "step": row.ingest_step,
                "percent": row.ingest_percent,
                "message": row.ingest_message,
                "error_message": row.error_message,
                "analysis_ready": bool(getattr(row, "analysis_ready", False)),
                "ingestion_started": bool(getattr(row, "ingestion_started", False)),
                "ingestion_completed": bool(getattr(row, "ingestion_completed", False)),
                "ingestion_failed": bool(getattr(row, "ingestion_failed", False)),
                "updated_at": row.updated_at or "",
            }
            data = json.dumps(payload)
            if data != last:
                last = data
                yield f"data: {data}\n\n"
            if row.status in ("completed", "failed"):
                return
            await asyncio.sleep(1.0)

    return StreamingResponse(event_gen(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# GET /api/ingest/diagnostic/{document_id} – Detailed ingestion diagnostic
# ---------------------------------------------------------------------------
@router.get("/api/ingest/diagnostic/{document_id}")
async def ingest_diagnostic(
    document_id: str,
    user: User = Depends(require_role(["admin"])),
    db: AsyncSession = Depends(get_db)
):
    """
    Detailed diagnostic endpoint for investigating document ingestion issues.
    Returns comprehensive information about text extraction, chunking, and embedding.
    """
    from app.db.models import Chunk, Embedding
    from sqlalchemy import func
    import os
    
    doc_int = _parse_document_id(document_id)
    result = await db.execute(select(DbDocument).where(DbDocument.id == doc_int))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Get file info
    file_size = 0
    file_exists = False
    try:
        if doc.path:
            file_exists = os.path.exists(doc.path)
            if file_exists:
                file_size = os.path.getsize(doc.path)
    except Exception:
        pass
    
    # Count chunks
    chunk_result = await db.execute(
        select(func.count(Chunk.id)).where(Chunk.document_id == doc_int)
    )
    chunk_count = chunk_result.scalar() or 0
    
    # Get sample chunks
    chunk_sample = []
    if chunk_count > 0:
        chunk_res = await db.execute(
            select(Chunk).where(Chunk.document_id == doc_int).limit(3)
        )
        for c in chunk_res.scalars():
            chunk_sample.append({
                "chunk_index": c.chunk_index,
                "text_length": len(c.text) if c.text else 0,
                "text_preview": (c.text[:200] + "...") if c.text and len(c.text) > 200 else c.text,
            })
    
    # Count embeddings
    emb_result = await db.execute(
        select(func.count(Embedding.id)).where(
            Embedding.id.in_(
                select(Chunk.embedding_id).where(Chunk.document_id == doc_int)
            )
        )
    )
    embedding_count = emb_result.scalar() or 0
    
    # Check ChromaDB
    chroma_count = 0
    try:
        from app.utils.chroma_client import chroma
        if doc.project_id:
            coll = chroma.get_collection(str(doc.project_id))
            # Count by metadata filter (approximate)
            all_ids = coll.get()["ids"]
            chroma_count = len([i for i in all_ids if i.startswith(f"chroma_{doc_int}_")])
    except Exception as e:
        chroma_count = f"Error: {str(e)}"
    
    return {
        "document_id": doc_int,
        "filename": doc.filename,
        "mime_type": doc.mime_type,
        "detected_type": doc.detected_type,
        "status": doc.status,
        "ingest_step": doc.ingest_step,
        "ingest_percent": doc.ingest_percent,
        "ingest_message": doc.ingest_message,
        "error_message": doc.error_message,
        "file": {
            "path": doc.path,
            "exists": file_exists,
            "size_bytes": file_size,
            "size_human": f"{file_size / 1024:.2f} KB" if file_size else "0 KB",
        },
        "database": {
            "chunk_count": chunk_count,
            "embedding_count": embedding_count,
            "chunk_sample": chunk_sample,
        },
        "chroma": {
            "project_id": doc.project_id,
            "estimated_vectors": chroma_count,
        },
        "embedding_metadata": {
            "embedding_provider": doc.embedding_provider,
            "embedding_model": doc.embedding_model,
            "embedding_version": doc.embedding_version,
            "embedded_at": str(doc.embedded_at) if doc.embedded_at else None,
        },
        "flags": {
            "ingestion_started": bool(getattr(doc, "ingestion_started", False)),
            "ingestion_completed": bool(getattr(doc, "ingestion_completed", False)),
            "ingestion_failed": bool(getattr(doc, "ingestion_failed", False)),
            "analysis_ready": bool(getattr(doc, "analysis_ready", False)),
        },
        "diagnosis": _diagnose_ingestion(doc, chunk_count, file_size),
    }

def _diagnose_ingestion(doc, chunk_count: int, file_size: int) -> dict:
    """Generate diagnostic assessment based on document state."""
    issues = []
    recommendations = []
    
    if not file_size or file_size == 0:
        issues.append("File size is 0 or file not found")
        recommendations.append("Check file exists at path and re-upload")
    
    if doc.status == "uploaded":
        issues.append("Document never started ingestion")
        recommendations.append("Trigger ingestion manually or restart worker")
    
    elif doc.status == "failed":
        issues.append(f"Ingestion failed at step: {doc.ingest_step}")
        if doc.error_message:
            issues.append(f"Error: {doc.error_message}")
        recommendations.append("Check logs for detailed error, then retry ingestion")
    
    elif doc.status == "ingesting":
        issues.append("Ingestion appears stuck or in progress")
        recommendations.append("Check if worker is running; may need to restart")
    
    elif doc.status in ("completed", "summarized", "embedded") and chunk_count == 0:
        issues.append("Ingestion completed but NO CHUNKS were created")
        issues.append("Text extraction likely produced empty or insufficient text")
        recommendations.append("Check PDF is text-based (not scanned image)")
        recommendations.append("Verify OCR is available for image-based PDFs")
        recommendations.append("Re-upload document and check extraction logs")
    
    if chunk_count == 0 and doc.ingest_step not in ("extract", "failed"):
        issues.append(f"No chunks in database despite reaching step: {doc.ingest_step}")
        recommendations.append("Investigate chunking logic in ingestion pipeline")
    
    return {
        "status": "healthy" if not issues else "issues_found",
        "issues": issues,
        "recommendations": recommendations,
    }
