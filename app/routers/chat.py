"""
Chat session endpoints for DocTel.
"""

import json

from app.routers.deps import (
    # stdlib
    datetime,
    uuid,
    # fastapi
    APIRouter,
    Body,
    Depends,
    HTTPException,
    Query,
    # starlette
    JSONResponse,
    # sqlalchemy
    AsyncSession,
    select,
    func,
    # config
    settings,
    # db
    get_db,
    # models
    User,
    DbSession,
    DbMessage,
    Document as DbDocument,
    # rbac
    get_current_user,
    check_project_access,
    ensure_project_membership,
    # helpers
    _parse_document_id,
    _assert_document_workspace_access,
    # utils
    update_installed_models,
    # logger
    logger,
)

router = APIRouter(tags=["chat"])


# Legacy stub kept only to avoid silent behavior changes for any old callers.
@router.post("/api/ask-legacy")
async def ask_question_legacy(
    project_id: int,
    user_query: str,
    session_id: int | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return JSONResponse(
        status_code=404,
        content={
            "error": "legacy_endpoint_removed",
            "message": "Use POST /api/ask with JSON {question, scope?, session_id?, model?} or POST /api/ask/{document_id} for document chat.",
        },
    )


@router.post("/api/chat/sessions")
async def create_chat_session(
    payload: dict = Body(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    payload = payload or {}
    project_id = payload.get("project_id")
    document_id = payload.get("document_id")
    scope = (payload.get("scope") or "").strip().lower() or None
    title = (payload.get("title") or "").strip()
    model_name = (payload.get("model") or payload.get("model_name") or "").strip() or None
    session_uuid = str(uuid.uuid4())
    resolved_project_id = None
    resolved_document_id = None
    if document_id:
        try:
            doc_int = _parse_document_id(str(document_id))
            res = await db.execute(select(DbDocument).where(DbDocument.id == doc_int))
            doc = res.scalar_one_or_none()
            if doc:
                await _assert_document_workspace_access(doc, user, db)
                resolved_project_id = int(doc.project_id)
                resolved_document_id = doc.id
                if not title:
                    title = (doc.filename or "").strip() or f"Document {doc_int}"
        except HTTPException:
            raise
        except Exception:
            resolved_project_id = None
    if project_id is not None:
        try:
            resolved_project_id = int(project_id)
        except Exception:
            pass
    if resolved_project_id is not None:
        await check_project_access(int(resolved_project_id), user, db)
        await ensure_project_membership(int(resolved_project_id), user, db, role_in_project="analyst")
    if not scope:
        scope = "document" if resolved_document_id is not None else ("project" if resolved_project_id is not None else "global")
    s = DbSession(
        project_id=resolved_project_id,
        document_id=resolved_document_id,
        user_id=user.id,
        session_uuid=session_uuid,
        model_name=model_name,
        title=title or "",
        scope=scope,
        archived=False,
    )
    db.add(s)
    await db.commit()
    return {"session_id": session_uuid, "model": model_name or ""}


@router.get("/api/chat/sessions/{session_id}/messages")
async def get_chat_messages(
    session_id: str,
    limit: int = 100,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(select(DbSession).where(DbSession.session_uuid == session_id))
    sess = res.scalar_one_or_none()
    if not sess:
        return JSONResponse(status_code=404, content={"error": "Session not found"})
    if sess.user_id is None:
        sess.user_id = user.id
        db.add(sess)
        await db.commit()
    if sess.project_id is not None:
        await check_project_access(int(sess.project_id), user, db)
        await ensure_project_membership(int(sess.project_id), user, db, role_in_project="analyst")
    elif sess.user_id != user.id and user.role != "admin":
        return JSONResponse(status_code=403, content={"error": "Access denied"})
    lim = max(1, min(200, int(limit)))
    mres = await db.execute(
        select(DbMessage).where(DbMessage.session_id == sess.id).order_by(DbMessage.created_at.asc()).limit(lim)
    )
    msgs = list(mres.scalars().all())
    items = []
    for m in msgs:
        citations = []
        if m.citations_json:
            try:
                citations = json.loads(m.citations_json) or []
            except Exception:
                citations = []
        items.append(
            {
                "id": m.id,
                "role": m.role,
                "content": m.content or "",
                "status": getattr(m, "status", "done") or "done",
                "citations": citations,
                "created_at": str(m.created_at) if m.created_at else "",
            }
        )

    # Update session's updated_at timestamp when messages are retrieved
    if msgs:
        sess.updated_at = datetime.datetime.now(datetime.timezone.utc)
        db.add(sess)
        await db.commit()

    return {"session_id": session_id, "messages": items, "model_name": sess.model_name or ""}


@router.post("/api/chat/sessions/{session_id}/model")
async def set_chat_session_model(
    session_id: str,
    payload: dict = Body(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.services.gemini_service import GEMINI_MODEL_ID
    from app.services.deepseek_service import DEEPSEEK_MODEL_ID

    model = (payload.get("model") or "").strip()
    if not model:
        return JSONResponse(status_code=400, content={"error": "missing_model"})
    res = await db.execute(select(DbSession).where(DbSession.session_uuid == session_id))
    sess = res.scalar_one_or_none()
    if not sess:
        return JSONResponse(status_code=404, content={"error": "Session not found"})
    if sess.user_id is None:
        sess.user_id = user.id
        db.add(sess)
        await db.commit()
    if sess.user_id != user.id:
        return JSONResponse(status_code=403, content={"error": "Access denied"})

    from app.utils.ollama_client import ollama
    from app.services.opencode_zen_service import is_configured as zen_configured

    is_cloud = model in (GEMINI_MODEL_ID, DEEPSEEK_MODEL_ID) or model.startswith("zen/") or model.startswith("go/") or model.startswith("huggingface/")
    installed: list[str] = []
    try:
        installed = await ollama.list_models()
        update_installed_models(installed)
    except Exception:
        if not is_cloud:
            return JSONResponse(
                status_code=503,
                content={
                    "error": "ollama_unreachable",
                    "message": "Ollama is not reachable. Start Ollama (ollama serve) and retry.",
                },
            )
    installed_set = set(installed or [])
    if is_cloud:
        installed_set.add(model)
    allowed = set(settings.available_models or []) | installed_set
    if model not in allowed:
        return JSONResponse(status_code=400, content={"error": "model_not_allowed", "model": model})
    if model not in installed_set:
        return JSONResponse(
            status_code=400,
            content={
                "error": "model_not_available",
                "message": f"Model {model} is not installed. Please pull it via Ollama.",
                "pull_command": f"ollama pull {model}",
            },
        )

    prev = sess.model_name
    sess.model_name = model
    db.add(sess)
    if prev and prev != model:
        db.add(
            DbMessage(
                session_id=sess.id,
                role="system",
                content=f"Model switched to {model}",
                status="done",
                citations_json="",
            )
        )
    await db.commit()
    return {"ok": True, "session_id": session_id, "model": model}


@router.get("/api/chat/sessions")
async def list_chat_sessions(
    project_id: int | None = None,
    limit: int = 50,
    page: int = 1,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    lim = max(1, min(200, int(limit)))
    pg = max(1, int(page))
    base_q = select(DbSession).where(DbSession.user_id == user.id).where((DbSession.archived == False) | (DbSession.archived.is_(None)))
    if project_id is not None:
        base_q = base_q.where(DbSession.project_id == int(project_id))
    count_q = select(func.count()).select_from(base_q.subquery())
    total_res = await db.execute(count_q)
    total = int(total_res.scalar() or 0)
    q = base_q.order_by(DbSession.updated_at.desc(), DbSession.started_at.desc()).offset((pg - 1) * lim).limit(lim)
    sres = await db.execute(q)
    sessions = list(sres.scalars().all())
    out = []
    for s in sessions:
        out.append(
            {
                "session_id": s.session_uuid,
                "project_id": str(s.project_id) if s.project_id is not None else None,
                "document_id": f"doc_{s.document_id}" if getattr(s, "document_id", None) is not None else None,
                "model": s.model_name or "",
                "started_at": str(s.started_at) if s.started_at else "",
                "updated_at": str(getattr(s, "updated_at", None) or s.started_at or ""),
                "title": getattr(s, "title", "") or "",
                "scope": getattr(s, "scope", "") or "",
            }
        )
    return {"sessions": out, "total": total, "page": pg, "page_size": lim}


@router.patch("/api/chat/sessions/{session_id}")
async def update_chat_session(
    session_id: str,
    payload: dict = Body(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(select(DbSession).where(DbSession.session_uuid == session_id))
    sess = res.scalar_one_or_none()
    if not sess:
        return JSONResponse(status_code=404, content={"error": "Session not found"})
    if sess.user_id != user.id and user.role != "admin":
        return JSONResponse(status_code=403, content={"error": "Access denied"})
    title = payload.get("title")
    archived = payload.get("archived")
    if isinstance(title, str):
        sess.title = title.strip()
    if isinstance(archived, bool):
        sess.archived = archived
    db.add(sess)
    await db.commit()
    return {"ok": True}


@router.delete("/api/chat/sessions/{session_id}")
async def delete_chat_session(
    session_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(select(DbSession).where(DbSession.session_uuid == session_id))
    sess = res.scalar_one_or_none()
    if not sess:
        return JSONResponse(status_code=404, content={"error": "Session not found"})
    if sess.user_id != user.id and user.role != "admin":
        return JSONResponse(status_code=403, content={"error": "Access denied"})
    sess.archived = True
    db.add(sess)
    await db.commit()
    return {"ok": True}
