"""
DocTel document management router.

Endpoints for listing, downloading, deleting, and re-assigning documents,
plus user-scoped document and project queries.
"""

import json

from pathlib import Path as FPath

from app.routers.deps import (
    APIRouter,
    Depends,
    HTTPException,
    Body,
    select,
    func,
    Document,
    Project,
    ProjectMember,
    User,
    DocAnalysis,
    SuggestedPrompt,
    AsyncSession,
    JSONResponse,
    FileResponse,
    get_current_user,
    get_db,
    require_role,
    check_project_access,
    ensure_project_membership,
    _parse_document_id,
    _assert_document_workspace_access,
    enqueue_ingest,
)

from app.services.document_permission_service import (
    assert_can_view,
    assert_can_download,
    assert_can_preview,
)
from app.services.audit_service import log_interaction
from app.db.models import Chunk

logger = __import__("logging").getLogger(__name__)

router = APIRouter(tags=["documents"])


# ---------------------------------------------------------------------------
# Helper – shared download logic (used only by the download route below)
# ---------------------------------------------------------------------------
async def _download_document_file(document_id: str, user: User, db: AsyncSession):
    doc_int = _parse_document_id(document_id)
    result = await db.execute(select(Document).where(Document.id == doc_int))
    doc = result.scalar_one_or_none()
    if not doc:
        return JSONResponse(status_code=404, content={"error": "Document not found"})
    await assert_can_download(doc, user, db)
    await log_interaction(
        db, user.id, "download_document", "document", f"doc_{doc.id}",
        {"filename": doc.filename, "project_id": doc.project_id},
    )
    path = FPath(doc.path)
    if not path.exists():
        return JSONResponse(status_code=404, content={"error": "file_missing"})
    return FileResponse(str(path), media_type=doc.mime_type or "application/octet-stream", filename=doc.filename)


# ---------------------------------------------------------------------------
# GET /api/documents — list documents with filters and pagination
# ---------------------------------------------------------------------------
@router.get("/api/documents")
async def list_documents(
    search: str | None = None,
    project_id: int | None = None,
    status: str | None = None,
    tag: str | None = None,
    visibility: str | None = None,
    page: int = 1,
    page_size: int = 50,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    page = max(1, int(page))
    page_size = max(1, min(200, int(page_size)))
    q = select(Document)
    if user.role != "admin":
        q = q.where((Document.uploaded_by_user_id == user.id) | (Document.is_public == True))
    if search:
        q = q.where(Document.filename.ilike(f"%{search}%"))
    if project_id is not None:
        q = q.where(Document.project_id == int(project_id))
    if status:
        q = q.where(Document.status == status.lower())
    if tag:
        q = q.where(Document.tags_json.ilike(f"%\"{tag}%"))
    if visibility == "public":
        q = q.where(Document.is_public == True)
    elif visibility == "private":
        q = q.where(Document.is_public == False)
    count_q = select(func.count()).select_from(q.subquery())
    total_res = await db.execute(count_q)
    total = int(total_res.scalar() or 0)
    q = q.order_by(Document.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    docs = list(result.scalars().all())

    # Batch-load doc_types for all documents (avoids N+1 queries)
    doc_ids = [d.id for d in docs]
    doc_type_rows = await db.execute(
        select(DocAnalysis.document_id, DocAnalysis.doc_type).where(
            DocAnalysis.document_id.in_(doc_ids)
        )
    )
    doc_type_map: dict = {}
    for row in doc_type_rows.all():
        doc_type_map[row.document_id] = row.doc_type

    items = []
    for d in docs:
        proj_name = ""
        if d.project_id is not None:
            pres = await db.execute(select(Project.name).where(Project.id == d.project_id))
            pn = pres.scalar_one_or_none()
            proj_name = pn or ""
        try:
            doc_tags = json.loads(d.tags_json) if d.tags_json else []
        except Exception:
            doc_tags = []
        doc_type: str | None = doc_type_map.get(d.id)

        items.append({
            "id": f"doc_{d.id}",
            "filename": d.filename,
            "project_id": str(d.project_id) if d.project_id is not None else None,
            "project_name": proj_name,
            "status": d.status or "uploaded",
            "doc_type": doc_type,
            "is_public": bool(getattr(d, "is_public", False)),
            "tags": doc_tags,
            "created_at": str(d.created_at) if getattr(d, "created_at", None) else "",
        })
    return {"documents": items, "total": total, "page": page, "page_size": page_size}


# ---------------------------------------------------------------------------
# GET /api/documents/{document_id}/download — download a document file
# ---------------------------------------------------------------------------
@router.get("/api/documents/{document_id}/download")
async def download_document_file_api(document_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await _download_document_file(document_id=document_id, user=user, db=db)


# ---------------------------------------------------------------------------
# GET /api/documents/{document_id}/preview/{chunk_index} — preview a chunk
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# GET /api/documents/{document_id}/chunks — list all chunks for a document
# ---------------------------------------------------------------------------
@router.get("/api/documents/{document_id}/chunks")
async def list_document_chunks(
    document_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    doc_int = _parse_document_id(document_id)
    doc_res = await db.execute(select(Document).where(Document.id == doc_int))
    doc = doc_res.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    await assert_can_view(doc, user, db)
    result = await db.execute(
        select(Chunk).where(Chunk.document_id == doc_int).order_by(Chunk.chunk_index)
    )
    chunks = list(result.scalars().all())
    await log_interaction(
        db, user.id, "list_chunks", "document", f"doc_{doc.id}",
        {"filename": doc.filename, "chunk_count": len(chunks)},
    )
    return {
        "document_id": document_id,
        "filename": doc.filename,
        "total_chunks": len(chunks),
        "chunks": [
            {
                "chunk_index": c.chunk_index,
                "text": c.text,
            }
            for c in chunks
        ],
    }


# ---------------------------------------------------------------------------
# GET /api/documents/{document_id}/preview/{chunk_index} — preview a chunk
# ---------------------------------------------------------------------------
@router.get("/api/documents/{document_id}/preview/{chunk_index}")
async def preview_chunk(
    document_id: str,
    chunk_index: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    doc_int = _parse_document_id(document_id)
    doc_res = await db.execute(select(Document).where(Document.id == doc_int))
    doc = doc_res.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    await assert_can_preview(doc, user, db)
    result = await db.execute(
        select(Chunk).where(Chunk.document_id == doc_int, Chunk.chunk_index == chunk_index)
    )
    chunk = result.scalar_one_or_none()
    if not chunk:
        raise HTTPException(status_code=404, detail="Chunk not found")
    await log_interaction(
        db, user.id, "preview_document", "document", f"doc_{doc.id}",
        {"filename": doc.filename, "chunk_index": chunk_index, "project_id": doc.project_id},
    )
    return {
        "chunk_index": chunk.chunk_index,
        "text": chunk.text,
        "document_id": document_id,
        "filename": doc.filename,
    }


# ---------------------------------------------------------------------------
# GET /api/documents/{document_id}/viewer — view document inline in browser
# ---------------------------------------------------------------------------
@router.get("/api/documents/{document_id}/viewer")
async def view_document_inline(
    document_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    doc_int = _parse_document_id(document_id)
    doc_res = await db.execute(select(Document).where(Document.id == doc_int))
    doc = doc_res.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    await assert_can_view(doc, user, db)
    await log_interaction(
        db, user.id, "view_document", "document", f"doc_{doc.id}",
        {"filename": doc.filename, "project_id": doc.project_id},
    )
    path = FPath(doc.path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="file_missing")
    return FileResponse(
        str(path),
        media_type=doc.mime_type or "application/octet-stream",
        filename=doc.filename,
        headers={"Content-Disposition": f'inline; filename="{doc.filename}"'},
    )


# ---------------------------------------------------------------------------
# DELETE /api/documents/{document_id} — delete a document and its analyses
# ---------------------------------------------------------------------------
@router.delete("/api/documents/{document_id}")
async def delete_document(document_id: str, user: User = Depends(require_role(["admin", "analyst"])), db: AsyncSession = Depends(get_db)):
    doc_int = _parse_document_id(document_id)
    result = await db.execute(select(Document).where(Document.id == doc_int))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    await _assert_document_workspace_access(doc, user, db)
    file_path = FPath(doc.path) if doc.path else None
    for analysis_res in [(await db.execute(select(DocAnalysis).where(DocAnalysis.document_id == doc_int).limit(1))).scalars().first()]:
        if analysis_res:
            await db.delete(analysis_res)
    for prompt_res in (await db.execute(select(SuggestedPrompt).where(SuggestedPrompt.document_id == doc_int))).scalars().all():
        await db.delete(prompt_res)
    await db.delete(doc)
    await db.commit()
    if file_path and file_path.exists():
        try:
            file_path.unlink()
        except Exception:
            pass
    return {"ok": True, "id": document_id}


# ---------------------------------------------------------------------------
# PUT /api/documents/{document_id}/project — move / unshare a document
# ---------------------------------------------------------------------------
@router.put("/api/documents/{document_id}/project")
async def override_document_project(
    document_id: str,
    payload: dict = Body(...),
    user: User = Depends(require_role(["admin", "analyst"])),
    db: AsyncSession = Depends(get_db),
):
    doc_int = _parse_document_id(document_id)
    pid = payload.get("project_id")
    if pid is None:
        return JSONResponse(status_code=400, content={"error": "missing_project_id"})
    res = await db.execute(select(Document).where(Document.id == doc_int))
    doc = res.scalar_one_or_none()
    if not doc:
        return JSONResponse(status_code=404, content={"error": "Document not found"})

    # Unshare: detach document from its project
    if str(pid) == "__none__":
        if user.role == "admin":
            pass
        elif int(getattr(doc, "uploaded_by_user_id", 0) or 0) == user.id:
            pass
        elif doc.project_id is not None:
            await check_project_access(int(doc.project_id), user, db)
        else:
            raise HTTPException(status_code=403, detail="Access denied")
        doc.project_id = None
        doc.needs_project_review = False
        doc.auto_project_confidence = 1.0
        doc.status = "uploaded"
        doc.ingest_step = "uploaded"
        doc.ingest_percent = 0
        doc.ingest_message = "Unshared from project"
        db.add(doc)
        await db.commit()
        return {"ok": True, "id": f"doc_{doc.id}", "project_id": None}

    # Share: move document to a different project
    await _assert_document_workspace_access(doc, user, db)
    try:
        pid_int = int(pid)
    except Exception:
        return JSONResponse(status_code=400, content={"error": "invalid_project_id"})
    await check_project_access(pid_int, user, db)
    await ensure_project_membership(pid_int, user, db, role_in_project="analyst")
    doc.project_id = pid_int
    doc.needs_project_review = False
    doc.auto_project_confidence = 1.0
    doc.status = "uploaded"
    doc.ingest_step = "uploaded"
    doc.ingest_percent = 0
    doc.ingest_message = "Project updated; queued for re-ingestion"
    db.add(doc)
    await db.commit()
    job_id = await enqueue_ingest("document_ingest", document_id=doc.id, owner_id=doc.owner_id)
    if job_id is None:
        logger.warning("[DOCUMENTS] Failed to enqueue ingest job for doc %s (owner=%s)", doc.id, doc.owner_id)
    return {"ok": True, "id": f"doc_{doc.id}", "project_id": str(pid_int)}


# ---------------------------------------------------------------------------
# GET /api/me/documents — documents visible to the current user
# ---------------------------------------------------------------------------
@router.get("/api/me/documents")
async def my_documents(page: int = 1, page_size: int = 50, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    pg = max(1, int(page))
    pg_sz = max(1, min(200, int(page_size)))
    if user.role == "admin":
        count_q = select(func.count(Document.id))
    else:
        member_ids_q = select(ProjectMember.project_id).where(ProjectMember.user_id == user.id)
        member_ids_res = await db.execute(member_ids_q)
        member_pids = [row[0] for row in member_ids_res.all()]
        owned_pids_q = select(Project.id).where(Project.owner_user_id == user.id)
        owned_pids_res = await db.execute(owned_pids_q)
        owned_pids = [row[0] for row in owned_pids_res.all()]
        accessible_pids = list(set(member_pids + owned_pids))
        base_where = (Document.uploaded_by_user_id == user.id) | (Document.is_public == True)
        if accessible_pids:
            base_where = base_where | (Document.project_id.in_(accessible_pids))
        count_q = select(func.count(Document.id)).where(base_where)
    total_res = await db.execute(count_q)
    total = int(total_res.scalar() or 0)
    if user.role == "admin":
        q = select(Document).order_by(Document.created_at.desc()).offset((pg - 1) * pg_sz).limit(pg_sz)
    else:
        base_where = (Document.uploaded_by_user_id == user.id) | (Document.is_public == True)
        if accessible_pids:
            base_where = base_where | (Document.project_id.in_(accessible_pids))
        q = select(Document).where(base_where).order_by(Document.created_at.desc()).offset((pg - 1) * pg_sz).limit(pg_sz)
    dres = await db.execute(q)
    docs = list(dres.scalars().all())
    # Batch-load doc_types for all documents (avoids N+1 queries)
    doc_ids = [d.id for d in docs]
    doc_type_rows = await db.execute(
        select(DocAnalysis.document_id, DocAnalysis.doc_type).where(
            DocAnalysis.document_id.in_(doc_ids)
        )
    )
    doc_type_map: dict = {}
    for row in doc_type_rows.all():
        doc_type_map[row.document_id] = row.doc_type

    items = []
    for d in docs:
        pres = await db.execute(select(Project).where(Project.id == d.project_id))
        p = pres.scalar_one_or_none()
        doc_type: str | None = doc_type_map.get(d.id)

        items.append(
            {
                "id": f"doc_{d.id}",
                "filename": d.filename,
                "project_id": str(d.project_id) if d.project_id is not None else None,
                "project_name": p.name if p else "",
                "status": d.status,
                "doc_type": doc_type,
                "is_public": bool(getattr(d, "is_public", False)),
                "created_at": str(d.created_at) if getattr(d, "created_at", None) else "",
                "download_url": f"/api/documents/doc_{d.id}/download",
                "view_url": f"/#doc_{d.id}",
                "needs_project_review": bool(getattr(d, "needs_project_review", False)),
                "auto_project_confidence": float(getattr(d, "auto_project_confidence", 0.0) or 0.0),
                "uploaded_by_me": d.uploaded_by_user_id == user.id,
            }
        )
    return {"documents": items, "total": total, "page": pg, "page_size": pg_sz}


# ---------------------------------------------------------------------------
# GET /users/me/documents — alias for my_documents
# ---------------------------------------------------------------------------
@router.get("/users/me/documents")
async def my_documents_alias(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await my_documents(user=user, db=db)
