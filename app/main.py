import os
import json
import yaml
import shutil
import re
import uvicorn
import logging
from logging.handlers import RotatingFileHandler
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Body
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import smtplib, ssl
from pathlib import Path
import asyncio
from starlette.responses import StreamingResponse
from starlette.responses import JSONResponse
from starlette.responses import FileResponse
import uuid
import datetime

from app.config import settings
from app.db.database import init_db, get_db, AsyncSessionLocal
from app.db.models import Project, Document, User, DocAnalysis, SuggestedPrompt, ProjectMember, Session, Diagram, Chunk, Embedding, UserIdentityProvider
from app.db.models import DocumentLink
from app.db.models import SystemSetting, SettingsAudit
from app.services.ingestion_service import ingest_document, get_file_hash
from app.services.rag_service import get_rag_answer, get_rag_answer_scoped
from app.services.vision_service import analyze_image
from app.security.rbac import get_current_user, require_role, check_project_access, ensure_project_membership
from sqlalchemy import select, func, delete, update
from app.services.auth_service import (
    verify_ad_credentials,
    request_email_code,
    verify_email_code,
    create_session,
)
from app.services.model_router import active as model_active, force_select as model_force
from app.services.ingest_worker import start_worker, enqueue as enqueue_ingest
from app.db.models import Document as DbDocument
from app.db.models import Session as DbSession, Message as DbMessage
from app.utils.model_cache import load_model_cache, update_installed_models, set_pull_state
from app.services.bootstrap_service import run_bootstrap_scan, start_watcher, get_bootstrap_status
from app.services.system_settings_service import (
    get_effective_settings,
    validate_settings_payload,
    apply_live_settings,
    restart_recommended_for_keys,
)
from app.services import auth_service

_ask_inflight: dict[str, float] = {}
_ask_lock = asyncio.Lock()

app = FastAPI(title="DocIntel")

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code == 401:
        detail = exc.detail
        if isinstance(detail, dict) and detail.get("error") == "token_expired":
            return JSONResponse(status_code=401, content={"error": "token_expired"})
        if detail == "token_expired":
            return JSONResponse(status_code=401, content={"error": "token_expired"})
    return JSONResponse(status_code=int(exc.status_code or 500), content={"detail": exc.detail})

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    try:
        logging.getLogger().exception("unhandled error")
    except Exception:
        pass
    return JSONResponse(status_code=500, content={"error": "internal_error"})

def _parse_document_id(document_id: str) -> int:
    if isinstance(document_id, str):
        match = re.match(r"^doc_(\d+)$", document_id.strip())
        if match:
            return int(match.group(1))
        if document_id.isdigit():
            return int(document_id)
    raise HTTPException(
        status_code=422,
        detail=[{
            "type": "int_parsing",
            "loc": ["path", "document_id"],
            "msg": "Input should be a valid integer, unable to parse string as an integer",
            "input": document_id,
        }],
    )

def _is_embedding_model(model: str) -> bool:
    m = (model or "").strip().lower()
    if not m:
        return False
    embed = (settings.embed_model or "").strip().lower()
    if embed and (m == embed or m.startswith(embed + ":")):
        return True
    if "embed" in m:
        return True
    return False

def _is_generation_model(model: str) -> bool:
    if not model:
        return False
    return not _is_embedding_model(model)

async def _accessible_project_ids(user: User, db: AsyncSession) -> list[int]:
    if user.role == "admin":
        res = await db.execute(select(Project.id))
        return [int(x) for x in res.scalars().all()]
    owned = await db.execute(select(Project.id).where(Project.owner_user_id == user.id))
    member = await db.execute(select(ProjectMember.project_id).where(ProjectMember.user_id == user.id))
    ids = list(dict.fromkeys([*owned.scalars().all(), *member.scalars().all()]))
    return [int(x) for x in ids if x is not None]

# Local-only: bind to localhost
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    await init_db()
    try:
        async with AsyncSessionLocal() as db:
            effective, _ = await get_effective_settings(db)
            apply_live_settings(effective)
    except Exception:
        pass
    log_path = settings.projects_dir.parent.parent / "logs" / "app.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(str(log_path), maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s level=%(levelname)s msg=%(message)s")
    handler.setFormatter(formatter)
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(logging.INFO)
    await start_worker()
    asyncio.create_task(run_bootstrap_scan())
    await start_watcher()

@app.get("/api/bootstrap/status")
async def api_bootstrap_status(user: User = Depends(get_current_user)):
    return get_bootstrap_status()

@app.post("/api/admin/reindex")
async def api_admin_reindex(user: User = Depends(require_role(["admin"]))):
    asyncio.create_task(run_bootstrap_scan())
    return {"ok": True}

@app.get("/healthz")
async def health():
    return {"status": "ok"}

@app.get("/api/health/app")
async def api_health_app():
    return {"ok": True}

@app.get("/api/health/ollama")
async def api_health_ollama():
    from app.utils.ollama_client import ollama
    try:
        models = await ollama.list_models()
        update_installed_models(models)
    except Exception:
        cache = load_model_cache()
        return {
            "ok": False,
            "reason": "unreachable",
            "hint": "Start Ollama (ollama serve) and retry.",
            "models": [],
            "installed": cache.get("installed") or [],
        }
    present = set(models)
    return {
        "ok": True,
        "models": models,
        "installed": models,
        "available": list(settings.available_models or []),
        "present": list(present),
    }

@app.get("/api/models/available")
async def api_models_available():
    from app.utils.ollama_client import ollama
    installed: list[str] = []
    try:
        installed = await ollama.list_models()
        update_installed_models(installed)
        offline = False
    except Exception:
        cache = load_model_cache()
        installed = list(cache.get("installed") or [])
        offline = True
    available = list(settings.available_models or [])
    installed_set = set(installed)
    available_set = set(available)
    merged = list(dict.fromkeys(available + installed))
    filtered_installed = [m for m in merged if m in installed_set]
    filtered_available = [m for m in merged if m in available_set or m in installed_set]
    filtered_installed = [m for m in filtered_installed if _is_generation_model(m)]
    filtered_available = [m for m in filtered_available if _is_generation_model(m)]
    return {
        "installed": filtered_installed,
        "available": filtered_available,
        "offline": offline,
        "default_model": (settings.default_model or settings.text_model),
        "embed_model": settings.embed_model,
        "vision_model": settings.vision_model,
    }

@app.get("/api/settings/ui")
async def api_settings_ui(user: User = Depends(get_current_user)):
    return settings.ui.model_dump()


@app.post("/api/models/pull")
async def api_models_pull(
    payload: dict = Body(...),
    user: User = Depends(get_current_user),
):
    model = (payload.get("model") or "").strip()
    resume = bool(payload.get("resume", True))
    if not model:
        return JSONResponse(status_code=400, content={"ok": False, "error": "missing_model"})
    if settings.available_models and model not in set(settings.available_models):
        return JSONResponse(status_code=400, content={"ok": False, "error": "model_not_allowed", "model": model})
    from app.services.model_pull_service import start_pull, get_status_payload

    await start_pull(model, resume=resume)
    return await get_status_payload(model)


@app.get("/api/models/pull/status/{model}")
async def api_models_pull_status(model: str, user: User = Depends(get_current_user)):
    from app.services.model_pull_service import get_status_payload

    m = (model or "").strip()
    if not m:
        return JSONResponse(status_code=400, content={"ok": False, "error": "missing_model"})
    return await get_status_payload(m)

# Readiness probe: DB + Ollama
@app.get("/readyz")
async def readyz(db: AsyncSession = Depends(get_db)):
    await db.execute(select(Project).limit(1))
    from app.utils.ollama_client import ollama
    try:
        models = await ollama.list_models()
    except Exception:
        return {"status": "not_ready", "reason": "ollama_unreachable"}
    return {"status": "ready", "models": models}

# Minimal metrics
_metrics = {"uploads_total": 0, "ingest_total": 0}

@app.get("/metrics")
async def metrics():
    return _metrics
# Projects
@app.post("/api/projects")
async def create_project(name: str, user: User = Depends(require_role(["admin", "analyst"])), db: AsyncSession = Depends(get_db)):
    project = Project(name=name, owner_user_id=user.id)
    db.add(project)
    await db.commit()
    await ensure_project_membership(project.id, user, db, role_in_project="admin" if user.role == "admin" else "analyst")
    return {"id": project.id, "name": project.name}

# Upload
@app.post("/api/upload")
async def upload_documents(
    project_id: int, 
    file: Optional[UploadFile] = File(None),
    files: Optional[List[UploadFile]] = File(None),
    title: Optional[str] = Form(None),
    date: Optional[str] = Form(None),
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
        
        doc = Document(
            project_id=project_id,
            uploaded_by_user_id=user.id,
            filename=file_item.filename,
            path=str(file_path),
            mime_type=file_item.content_type,
            sha256=sha256,
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
        await enqueue_ingest(doc.id)
        
        # Start background ingestion
        # asyncio.create_task(ingest_document(doc.id, db))
        # Note: In a real app, we'd use a background task with a fresh DB session
        uploaded_docs.append({"id": f"doc_{doc.id}", "filename": doc.filename, "status": doc.status, "detected_type": doc.detected_type})
        
    return {"documents": uploaded_docs}

# Ingest (manual trigger)
@app.post("/api/ingest/{doc_id}")
async def trigger_ingestion(
    doc_id: int, 
    user: User = Depends(require_role(["admin", "analyst"])), 
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(DbDocument).where(DbDocument.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    await check_project_access(doc.project_id, user, db)
    await ensure_project_membership(doc.project_id, user, db, role_in_project="analyst")
    await enqueue_ingest(doc_id)
    return {"status": "queued"}

# Ask (RAG)
@app.post("/api/ask")
async def ask_question(
    project_id: int, 
    user_query: str, 
    session_id: Optional[int] = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return JSONResponse(
        status_code=404,
        content={"error": "Chat endpoint not found. Use POST /api/ask/{document_id} with JSON {question, project_id, session_id?}."},
    )


@app.post("/api/chat/sessions")
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
                resolved_project_id = int(doc.project_id)
                resolved_document_id = int(doc.id)
                if not title:
                    title = (doc.filename or "").strip() or f"Document {doc_int}"
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
    return {"session_id": session_uuid}


@app.get("/api/chat/sessions/{session_id}/messages")
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
    return {"session_id": session_id, "messages": items}


@app.post("/api/chat/sessions/{session_id}/model")
async def set_chat_session_model(
    session_id: str,
    payload: dict = Body(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
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
    try:
        installed = await ollama.list_models()
        update_installed_models(installed)
    except Exception:
        return JSONResponse(
            status_code=503,
            content={
                "error": "ollama_unreachable",
                "message": "Ollama is not reachable. Start Ollama (ollama serve) and retry.",
            },
        )
    installed_set = set(installed or [])
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

@app.post("/api/ask/{document_id}")
async def ask_document(
    document_id: str,
    payload: dict = Body(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    doc_int = _parse_document_id(document_id)
    result = await db.execute(select(DbDocument).where(DbDocument.id == doc_int))
    doc = result.scalar_one_or_none()
    if not doc:
        return JSONResponse(status_code=404, content={"error": "Document not found"})
    await check_project_access(doc.project_id, user, db)
    await ensure_project_membership(doc.project_id, user, db, role_in_project="analyst")

    question = (payload.get("question") or "").strip()
    if not question:
        return JSONResponse(status_code=400, content={"error": "Missing question"})

    session_uuid = (payload.get("session_id") or "").strip() or None
    requested_model = (payload.get("model") or "").strip() or None
    scope = (payload.get("scope") or "project").strip().lower()
    force_policy = bool(payload.get("force_policy", False))
    force_diagram = bool(payload.get("force_diagram", False))
    if not session_uuid:
        session_uuid = str(uuid.uuid4())
        s = DbSession(project_id=int(doc.project_id), user_id=user.id, session_uuid=session_uuid, model_name=requested_model)
        db.add(s)
        await db.commit()
    else:
        sres = await db.execute(select(DbSession).where(DbSession.session_uuid == session_uuid))
        s = sres.scalar_one_or_none()
        if not s:
            s = DbSession(project_id=int(doc.project_id), user_id=user.id, session_uuid=session_uuid, model_name=requested_model)
            db.add(s)
            await db.commit()
        await check_project_access(s.project_id, user, db)

    inflight_key = f"{session_uuid}:{doc_int}"
    async with _ask_lock:
        if inflight_key in _ask_inflight:
            return JSONResponse(
                status_code=409,
                content={"error": "ask_in_progress", "session_id": session_uuid, "expected_ms": 3000},
            )
        _ask_inflight[inflight_key] = asyncio.get_event_loop().time()

    try:
        pending_message_id = payload.get("pending_message_id")
        user_msg = None
        if pending_message_id is not None:
            try:
                mid = int(pending_message_id)
            except Exception:
                mid = None
            if mid is not None:
                mres = await db.execute(select(DbMessage).where(DbMessage.id == mid))
                existing = mres.scalar_one_or_none()
                if existing and existing.session_id == s.id and existing.role == "user":
                    user_msg = existing

        if not user_msg:
            user_msg = DbMessage(session_id=s.id, role="user", content=question, status="pending", citations_json="")
            db.add(user_msg)
            await db.commit()

        from app.utils.ollama_client import ollama

        ares = await db.execute(select(DocAnalysis.id).where(DocAnalysis.document_id == doc_int))
        if ares.first():
            if doc.status != "completed":
                doc.status = "completed"
                doc.ingest_step = "done"
                doc.ingest_percent = 100
                doc.ingest_message = "Completed"
                doc.error_message = ""
            doc.analysis_ready = True
            doc.ingestion_started = True
            doc.ingestion_completed = True
            doc.ingestion_failed = False
            db.add(doc)
            await db.commit()

        if doc.status == "uploaded":
            age_s = 0.0
            try:
                if getattr(doc, "created_at", None):
                    dt = doc.created_at
                    if getattr(dt, "tzinfo", None) is None:
                        dt = dt.replace(tzinfo=datetime.timezone.utc)
                    age_s = (datetime.datetime.now(datetime.timezone.utc) - dt).total_seconds()
            except Exception:
                age_s = 0.0
            if age_s > 5 and not bool(getattr(doc, "ingestion_started", False)):
                doc.status = "ingesting"
                doc.ingest_step = "extract"
                doc.ingest_percent = 0
                doc.ingest_message = "Queued for ingestion"
                doc.ingestion_started = True
                db.add(doc)
                await db.commit()
                await enqueue_ingest(int(doc.id))

        allow_while = bool(getattr(settings, "ui", None) and getattr(settings.ui, "allow_chat_while_ingesting", True))

        if doc.status not in ("completed", "summarized", "embedded") and not allow_while and doc.status != "failed":
            wait_msg = DbMessage(
                session_id=s.id,
                role="system",
                content=f"Analysis is still running (step: {doc.ingest_step}, {doc.ingest_percent}%). I will answer when ready.",
                status="done",
                citations_json="",
            )
            db.add(user_msg)
            db.add(wait_msg)
            await db.commit()
            return JSONResponse(
                status_code=202,
                content={
                    "status": "pending_analysis",
                    "reason": "analysis_not_ready",
                    "document_status": doc.status,
                    "retry_after_ms": 4000,
                    "poll_url": f"/api/ingest/{document_id}/status",
                    "session_id": session_uuid,
                    "pending_message_id": user_msg.id,
                },
            )

        try:
            models = await ollama.list_models()
            update_installed_models(models)
        except Exception:
            user_msg.status = "failed"
            db.add(user_msg)
            await db.commit()
            return JSONResponse(
                status_code=503,
                content={
                    "error": "ollama_unreachable",
                    "message": "Ollama is not reachable. Start Ollama (ollama serve) and retry.",
                    "retry_after_ms": 4000,
                    "session_id": session_uuid,
                },
            )
        if not models:
            user_msg.status = "failed"
            db.add(user_msg)
            await db.commit()
            return JSONResponse(
                status_code=503,
                content={
                    "error": "ollama_unreachable",
                    "message": "Ollama returned no installed models. Pull a model and retry.",
                    "retry_after_ms": 4000,
                    "session_id": session_uuid,
                },
            )
        present = set(models)
        embed_available = settings.embed_model in present

        allowed = set(settings.available_models or []) | present
        session_model = (s.model_name or "").strip() or None
        default_model = (settings.default_model or settings.text_model).strip()
        chosen_model = requested_model or session_model or default_model
        if not _is_generation_model(chosen_model):
            user_msg.status = "failed"
            db.add(user_msg)
            await db.commit()
            return JSONResponse(status_code=400, content={"error": "invalid_generation_model", "model": chosen_model})
        if chosen_model not in allowed:
            user_msg.status = "failed"
            db.add(user_msg)
            await db.commit()
            return JSONResponse(status_code=400, content={"error": "model_not_allowed", "model": chosen_model})
        if chosen_model not in present:
            user_msg.status = "failed"
            db.add(user_msg)
            await db.commit()
            return JSONResponse(
                status_code=400,
                content={
                    "error": "model_not_available",
                    "message": f"Model {chosen_model} is not installed. Please pull it via Ollama.",
                    "pull_command": f"ollama pull {chosen_model}",
                },
            )
        if not session_model and chosen_model:
            s.model_name = chosen_model
            db.add(s)
            await db.commit()
        if requested_model and requested_model != session_model:
            prev = session_model
            s.model_name = requested_model
            db.add(s)
            if prev and prev != requested_model:
                db.add(
                    DbMessage(
                        session_id=s.id,
                        role="system",
                        content=f"Model switched to {requested_model}",
                        status="done",
                        citations_json="",
                    )
                )
            await db.commit()

        project_ids = [int(doc.project_id)]
        document_filter = None
        if scope == "all":
            project_ids = await _accessible_project_ids(user, db)
        rag = None
        try:
            if embed_available:
                rag = await get_rag_answer_scoped(
                    project_ids,
                    question,
                    db,
                    document_id=document_filter,
                    model_name=chosen_model,
                    force_policy=force_policy,
                    force_diagram=force_diagram,
                )
        except Exception:
            rag = None
        if not rag:
            sys_prompt = (settings.zetdc.system_prompt or "").strip() or None
            answer_text = await ollama.generate(chosen_model, question, system=sys_prompt)
            rag = {"answer_text": answer_text, "citations": [], "cross_references": [], "used_model": chosen_model}
        user_msg.status = "done"
        db.add(user_msg)
        assistant = DbMessage(
            session_id=s.id,
            role="assistant",
            content=rag.get("answer_text", ""),
            status="done",
            citations_json=json.dumps(rag.get("citations", [])),
        )
        db.add(assistant)
        try:
            s.updated_at = datetime.datetime.now(datetime.timezone.utc)
            db.add(s)
        except Exception:
            pass
        await db.commit()
        return {
            "answer": rag.get("answer_text", ""),
            "citations": rag.get("citations", []),
            "cross_references": rag.get("cross_references", []),
            "used_model": rag.get("used_model", ""),
            "session_id": session_uuid,
        }
    except HTTPException:
        raise
    except Exception as e:
        try:
            logging.getLogger().exception("ask_document error")
        except Exception:
            pass
        return JSONResponse(status_code=500, content={"error": "internal_error", "detail": str(e)})
    finally:
        async with _ask_lock:
            _ask_inflight.pop(inflight_key, None)

@app.post("/api/ask")
async def ask_global(
    payload: dict = Body(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    question = (payload.get("question") or "").strip()
    if not question:
        return JSONResponse(status_code=400, content={"error": "Missing question"})
    scope = (payload.get("scope") or "all").strip().lower()
    requested_model = (payload.get("model") or "").strip() or None
    force_policy = bool(payload.get("force_policy", False))
    force_diagram = bool(payload.get("force_diagram", False))

    project_ids: list[int] = []
    project_id = payload.get("project_id")
    if scope == "project":
        if project_id is None:
            return JSONResponse(status_code=400, content={"error": "missing_project_id"})
        try:
            pid = int(project_id)
        except Exception:
            return JSONResponse(status_code=400, content={"error": "invalid_project_id"})
        await check_project_access(pid, user, db)
        await ensure_project_membership(pid, user, db, role_in_project="analyst")
        project_ids = [pid]
    else:
        project_ids = await _accessible_project_ids(user, db)
        if not project_ids:
            return JSONResponse(status_code=403, content={"error": "no_accessible_projects"})

    session_uuid = (payload.get("session_id") or "").strip() or None
    if not session_uuid:
        session_uuid = str(uuid.uuid4())
        s = DbSession(project_id=project_ids[0] if project_ids else None, user_id=user.id, session_uuid=session_uuid, model_name=requested_model)
        db.add(s)
        await db.commit()
    else:
        sres = await db.execute(select(DbSession).where(DbSession.session_uuid == session_uuid))
        s = sres.scalar_one_or_none()
        if not s:
            s = DbSession(project_id=project_ids[0] if project_ids else None, user_id=user.id, session_uuid=session_uuid, model_name=requested_model)
            db.add(s)
            await db.commit()
        if s.user_id != user.id:
            return JSONResponse(status_code=403, content={"error": "Access denied"})

    user_msg = DbMessage(session_id=s.id, role="user", content=question, status="pending", citations_json="")
    db.add(user_msg)
    await db.commit()

    from app.utils.ollama_client import ollama
    try:
        models = await ollama.list_models()
        update_installed_models(models)
    except Exception:
        user_msg.status = "failed"
        db.add(user_msg)
        await db.commit()
        return JSONResponse(status_code=503, content={"error": "ollama_unreachable"})
    present = set(models or [])
    embed_available = settings.embed_model in present

    allowed = set(settings.available_models or []) | present
    session_model = (s.model_name or "").strip() or None
    default_model = (settings.default_model or settings.text_model).strip()
    chosen_model = requested_model or session_model or default_model
    if not _is_generation_model(chosen_model):
        user_msg.status = "failed"
        db.add(user_msg)
        await db.commit()
        return JSONResponse(status_code=400, content={"error": "invalid_generation_model", "model": chosen_model})
    if chosen_model not in allowed:
        user_msg.status = "failed"
        db.add(user_msg)
        await db.commit()
        return JSONResponse(status_code=400, content={"error": "model_not_allowed", "model": chosen_model})
    if chosen_model not in present:
        user_msg.status = "failed"
        db.add(user_msg)
        await db.commit()
        return JSONResponse(status_code=400, content={"error": "model_not_available", "model": chosen_model})
    if not session_model:
        s.model_name = chosen_model
        db.add(s)
        await db.commit()

    rag = None
    if embed_available:
        try:
            rag = await get_rag_answer_scoped(
                project_ids,
                question,
                db,
                document_id=None,
                model_name=chosen_model,
                force_policy=force_policy,
                force_diagram=force_diagram,
            )
        except Exception:
            rag = None
    if not rag:
        sys_prompt = (settings.zetdc.system_prompt or "").strip() or None
        answer_text = await ollama.generate(chosen_model, question, system=sys_prompt)
        rag = {"answer_text": answer_text, "citations": [], "cross_references": [], "used_model": chosen_model}
    user_msg.status = "done"
    db.add(user_msg)
    assistant = DbMessage(
        session_id=s.id,
        role="assistant",
        content=rag.get("answer_text", ""),
        status="done",
        citations_json=json.dumps(rag.get("citations", [])),
    )
    db.add(assistant)
    try:
        s.updated_at = datetime.datetime.now(datetime.timezone.utc)
        db.add(s)
    except Exception:
        pass
    await db.commit()
    return {
        "answer": rag.get("answer_text", ""),
        "citations": rag.get("citations", []),
        "cross_references": rag.get("cross_references", []),
        "used_model": rag.get("used_model", ""),
        "session_id": session_uuid,
    }

@app.post("/api/generate/policy")
async def generate_policy(payload: dict = Body(...), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    topic = (payload.get("topic") or payload.get("question") or "").strip()
    if not topic:
        return JSONResponse(status_code=400, content={"error": "missing_topic"})
    scope = (payload.get("scope") or "all").strip().lower()
    model = (payload.get("model") or "").strip() or None
    project_ids = await _accessible_project_ids(user, db) if scope == "all" else []
    if scope == "project":
        pid = payload.get("project_id")
        if pid is None:
            return JSONResponse(status_code=400, content={"error": "missing_project_id"})
        pid_int = int(pid)
        await check_project_access(pid_int, user, db)
        project_ids = [pid_int]
    rag = await get_rag_answer_scoped(project_ids, topic, db, model_name=model, force_policy=True, force_diagram=False)
    return {"policy": rag.get("answer_text", ""), "citations": rag.get("citations", []), "used_model": rag.get("used_model", "")}

@app.post("/api/flowchart")
async def generate_flowchart(payload: dict = Body(...), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    question = (payload.get("topic") or payload.get("question") or "").strip()
    if not question:
        return JSONResponse(status_code=400, content={"error": "missing_topic"})
    scope = (payload.get("scope") or "all").strip().lower()
    model = (payload.get("model") or "").strip() or None
    project_ids = await _accessible_project_ids(user, db) if scope == "all" else []
    pid_int = None
    if scope == "project":
        pid = payload.get("project_id")
        if pid is None:
            return JSONResponse(status_code=400, content={"error": "missing_project_id"})
        pid_int = int(pid)
        await check_project_access(pid_int, user, db)
        project_ids = [pid_int]
    rag = await get_rag_answer_scoped(project_ids, question, db, model_name=model, force_policy=False, force_diagram=True)
    mermaid = rag.get("mermaid_code", "")
    drawing_prompt = rag.get("drawing_prompt", "")
    try:
        sess_uuid = (payload.get("session_id") or "").strip() or None
        sess_id = None
        if sess_uuid:
            sres = await db.execute(select(DbSession).where(DbSession.session_uuid == sess_uuid))
            sess = sres.scalar_one_or_none()
            if sess:
                sess_id = sess.id
                if pid_int is None:
                    pid_int = int(sess.project_id) if sess.project_id is not None else None
        if pid_int is not None:
            d = Diagram(project_id=pid_int, session_id=sess_id, title=payload.get("title") or question[:80], mermaid=mermaid, drawing_prompt=drawing_prompt, version=1)
            db.add(d)
            await db.commit()
    except Exception:
        pass
    return {"mermaid": mermaid, "drawing_prompt": drawing_prompt, "answer": rag.get("answer_text", ""), "citations": rag.get("citations", []), "used_model": rag.get("used_model", "")}

# --------------------------
# Public REST (root paths)
# --------------------------

@app.get("/projects")
async def list_projects(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = []
    if user.role == "admin":
        result = await db.execute(select(Project))
        rows = result.scalars().all()
    else:
        result = await db.execute(select(Project).where(Project.owner_user_id == user.id))
        rows = result.scalars().all()
    items = []
    for p in rows:
        c = await db.execute(select(func.count(Document.id)).where(Document.project_id == p.id))
        doc_count = int(c.scalar() or 0)
        items.append({"id": str(p.id), "name": p.name, "document_count": doc_count})
    return {"projects": items}

@app.get("/projects/{project_id}/documents")
async def list_project_documents(project_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await check_project_access(project_id, user, db)
    result = await db.execute(select(Document).where(Document.project_id == project_id))
    docs = result.scalars().all()
    out = []
    for d in docs:
        out.append({"id": f"doc_{d.id}", "filename": d.filename, "mime_type": d.mime_type})
    return {"project_id": str(project_id), "documents": out}

@app.get("/documents/{document_id}/file")
async def download_document_file(document_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    doc_int = _parse_document_id(document_id)
    result = await db.execute(select(Document).where(Document.id == doc_int))
    doc = result.scalar_one_or_none()
    if not doc:
        return JSONResponse(status_code=404, content={"error": "Document not found"})
    await check_project_access(int(doc.project_id), user, db)
    await ensure_project_membership(int(doc.project_id), user, db, role_in_project="analyst")
    path = Path(doc.path)
    if not path.exists():
        return JSONResponse(status_code=404, content={"error": "file_missing"})
    return FileResponse(str(path), media_type=doc.mime_type or "application/octet-stream", filename=doc.filename)

@app.get("/api/documents/{document_id}/download")
async def download_document_file_api(document_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await download_document_file(document_id=document_id, user=user, db=db)

@app.put("/api/documents/{document_id}/project")
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
    try:
        pid_int = int(pid)
    except Exception:
        return JSONResponse(status_code=400, content={"error": "invalid_project_id"})
    res = await db.execute(select(Document).where(Document.id == doc_int))
    doc = res.scalar_one_or_none()
    if not doc:
        return JSONResponse(status_code=404, content={"error": "Document not found"})
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
    await enqueue_ingest(doc.id)
    return {"ok": True, "id": f"doc_{doc.id}", "project_id": str(pid_int)}

@app.get("/api/me/projects")
async def my_projects(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if user.role == "admin":
        pres = await db.execute(select(Project))
        projects = list(pres.scalars().all())
        return {"projects": [{"id": str(p.id), "name": p.name, "role": "admin"} for p in projects]}
    owned_res = await db.execute(select(Project).where(Project.owner_user_id == user.id))
    owned = list(owned_res.scalars().all())
    member_res = await db.execute(select(ProjectMember).where(ProjectMember.user_id == user.id))
    members = list(member_res.scalars().all())
    proj_map: dict[int, dict] = {}
    for p in owned:
        proj_map[int(p.id)] = {"id": str(p.id), "name": p.name, "role": "owner"}
    if members:
        mids = [int(m.project_id) for m in members if m.project_id is not None]
        if mids:
            pres = await db.execute(select(Project).where(Project.id.in_(mids)))
            for p in pres.scalars().all():
                if int(p.id) in proj_map:
                    continue
                role = next((m.role_in_project for m in members if int(m.project_id) == int(p.id)), "analyst")
                proj_map[int(p.id)] = {"id": str(p.id), "name": p.name, "role": role}
    return {"projects": list(proj_map.values())}

@app.get("/users/me/projects")
async def my_projects_alias(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await my_projects(user=user, db=db)

@app.get("/api/me/documents")
async def my_documents(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if user.role == "admin":
        dres = await db.execute(select(Document))
        docs = list(dres.scalars().all())
    else:
        dres = await db.execute(select(Document).where(Document.uploaded_by_user_id == user.id))
        docs = list(dres.scalars().all())
    items = []
    for d in docs:
        pres = await db.execute(select(Project).where(Project.id == d.project_id))
        p = pres.scalar_one_or_none()
        items.append(
            {
                "id": f"doc_{d.id}",
                "filename": d.filename,
                "project_id": str(d.project_id) if d.project_id is not None else None,
                "project_name": p.name if p else "",
                "status": d.status,
                "created_at": str(d.created_at) if getattr(d, "created_at", None) else "",
                "download_url": f"/api/documents/doc_{d.id}/download",
                "view_url": f"/#doc_{d.id}",
                "needs_project_review": bool(getattr(d, "needs_project_review", False)),
                "auto_project_confidence": float(getattr(d, "auto_project_confidence", 0.0) or 0.0),
            }
        )
    return {"documents": items}

@app.get("/users/me/documents")
async def my_documents_alias(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await my_documents(user=user, db=db)

@app.get("/api/chat/sessions")
async def list_chat_sessions(
    project_id: Optional[int] = None,
    limit: int = 50,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    lim = max(1, min(200, int(limit)))
    q = select(DbSession).where(DbSession.user_id == user.id).where((DbSession.archived == False) | (DbSession.archived.is_(None)))
    if project_id is not None:
        q = q.where(DbSession.project_id == int(project_id))
    q = q.order_by(DbSession.updated_at.desc(), DbSession.started_at.desc()).limit(lim)
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
    return {"sessions": out}

@app.patch("/api/chat/sessions/{session_id}")
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

@app.delete("/api/chat/sessions/{session_id}")
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

@app.post("/documents")
async def upload_document_single(
    file: UploadFile = File(...),
    project_id: Optional[int] = Form(None),
    project_name: Optional[str] = Form(None),
    document_type: Optional[str] = Form(None),
    document_date: Optional[str] = Form(None),
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
    doc = Document(
        project_id=pid,
        uploaded_by_user_id=user.id,
        filename=file.filename,
        path=str(dest),
        mime_type=file.content_type,
        sha256=sha256,
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
    await enqueue_ingest(doc.id)
    return {"id": f"doc_{doc.id}", "filename": doc.filename, "status": "uploaded", "detected_type": doc.detected_type, "metadata": {
        "project_id": str(pid), "document_type": document_type, "document_date": document_date
    }}

@app.get("/api/ingest/status")
async def ingest_status(document_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    doc_int = _parse_document_id(document_id)
    result = await db.execute(select(DbDocument).where(DbDocument.id == doc_int))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    await check_project_access(doc.project_id, user, db)
    await ensure_project_membership(doc.project_id, user, db, role_in_project="analyst")
    if doc.status == "ingesting" and (doc.updated_at or "").strip():
        try:
            ts = doc.updated_at.replace("Z", "+00:00")
            dt = datetime.datetime.fromisoformat(ts)
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

@app.get("/api/ingest/{document_id}/status")
async def ingest_status_alias(document_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await ingest_status(document_id=document_id, user=user, db=db)

@app.get("/api/ingest/stream")
async def ingest_stream(document_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    doc_int = _parse_document_id(document_id)
    result = await db.execute(select(DbDocument).where(DbDocument.id == doc_int))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    await check_project_access(doc.project_id, user, db)
    await ensure_project_membership(doc.project_id, user, db, role_in_project="analyst")

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

@app.post("/api/ingest/retry")
async def ingest_retry(payload: dict = Body(...), user: User = Depends(require_role(["admin", "analyst"])), db: AsyncSession = Depends(get_db)):
    doc_int = _parse_document_id(payload.get("document_id", ""))
    result = await db.execute(select(DbDocument).where(DbDocument.id == doc_int))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    await check_project_access(doc.project_id, user, db)
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
    db.add(doc)
    await db.commit()
    await enqueue_ingest(doc.id)
    return {"ok": True}

# Vision
@app.post("/api/vision/ask")
async def ask_vision(
    image: UploadFile = File(...),
    user_query: str = Form(...),
    user: User = Depends(get_current_user)
):
    # Save image temporarily
    temp_path = settings.uploads_dir / f"vision_{image.filename}"
    with open(temp_path, "wb") as f:
        f.write(await image.read())
        
    result = await analyze_image(str(temp_path), user_query)
    return {"answer": result}

# --------------------------
# Compatibility Endpoints
# --------------------------

# Auth stub for frontend login
@app.post("/auth/login")
async def login(payload: dict = Body(...), db: AsyncSession = Depends(get_db)):
    ec_number = (payload.get("ec_number") or payload.get("username") or "").strip()
    password = (payload.get("password") or "").strip()
    if not ec_number or not password:
        raise HTTPException(status_code=400, detail="Missing credentials")
    display_name = None
    ad_email = None
    try:
        ad = verify_ad_credentials(ec_number, password)
        display_name = ad.get("display_name")
        ad_email = ad.get("email")
    except HTTPException as e:
        if settings.environment == "production":
            raise
        display_name = ec_number
    if not ad_email and settings.allowed_email_domain and "@" not in ec_number:
        ad_email = f"{ec_number}@{settings.allowed_email_domain}".lower()

    provider = "ec_password"
    identity = ec_number
    ures = await db.execute(select(UserIdentityProvider).where(UserIdentityProvider.provider == provider, UserIdentityProvider.identity == identity))
    prov = ures.scalar_one_or_none()
    user = None
    if prov:
        resu = await db.execute(select(User).where(User.id == prov.user_id))
        user = resu.scalar_one_or_none()
    if not user:
        resu = await db.execute(select(User).where((User.ec_number == ec_number) | (User.username == ec_number)))
        user = resu.scalar_one_or_none()
    if not user:
        user = User(username=ec_number, ec_number=ec_number, email=ad_email, display_name=display_name or ec_number, role="analyst")
        db.add(user)
        await db.commit()
    if not user.ec_number:
        user.ec_number = ec_number
    if ad_email and not user.email:
        user.email = ad_email
    if display_name and not user.display_name:
        user.display_name = display_name
    db.add(user)
    await db.commit()

    ures = await db.execute(select(UserIdentityProvider).where(UserIdentityProvider.provider == provider, UserIdentityProvider.identity == identity))
    prov = ures.scalar_one_or_none()
    if not prov:
        prov = UserIdentityProvider(user_id=user.id, provider=provider, identity=identity, verified=True)
    prov.last_login_at = datetime.datetime.now(datetime.timezone.utc)
    prov.verified = True
    db.add(prov)
    if user.email:
        eres = await db.execute(select(UserIdentityProvider).where(UserIdentityProvider.provider == "email_otp", UserIdentityProvider.identity == user.email))
        eprov = eres.scalar_one_or_none()
        if eprov and eprov.user_id and int(eprov.user_id) != int(user.id):
            primary_id = int(eprov.user_id)
            secondary_id = int(user.id)
            await db.execute(update(Project).where(Project.owner_user_id == secondary_id).values(owner_user_id=primary_id))
            await db.execute(update(ProjectMember).where(ProjectMember.user_id == secondary_id).values(user_id=primary_id))
            await db.execute(update(Document).where(Document.uploaded_by_user_id == secondary_id).values(uploaded_by_user_id=primary_id))
            await db.execute(update(Session).where(Session.user_id == secondary_id).values(user_id=primary_id))
            await db.execute(update(SystemSetting).where(SystemSetting.updated_by_user_id == secondary_id).values(updated_by_user_id=primary_id))
            await db.execute(update(SettingsAudit).where(SettingsAudit.changed_by_user_id == secondary_id).values(changed_by_user_id=primary_id))
            await db.execute(update(UserIdentityProvider).where(UserIdentityProvider.user_id == secondary_id).values(user_id=primary_id))
            await db.execute(delete(User).where(User.id == secondary_id))
            await db.commit()
            resu = await db.execute(select(User).where(User.id == primary_id))
            user = resu.scalar_one_or_none()
            if not user:
                raise HTTPException(status_code=500, detail="User merge failed")
            prov.user_id = user.id
            db.add(prov)
            eprov.user_id = user.id
        if not eprov:
            eprov = UserIdentityProvider(user_id=user.id, provider="email_otp", identity=user.email, verified=True)
        eprov.last_login_at = datetime.datetime.now(datetime.timezone.utc)
        eprov.verified = True
        db.add(eprov)
    await db.commit()

    token = create_session(user.id, user.display_name or display_name, provider, identity)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": user.id,
        "ec_number": user.ec_number or ec_number,
        "email": user.email or "",
        "display_name": user.display_name or display_name,
        "role": user.role,
    }

@app.post("/auth/logout")
async def logout(request: Request):
    authz = request.headers.get("authorization") or ""
    parts = authz.split(" ", 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        token = parts[1].strip()
        if token and not token.startswith("local-"):
            try:
                auth_service.revoke_token(token)
            except Exception:
                pass
    return {"success": True}

@app.get("/users/me")
async def users_me(user: User = Depends(get_current_user)):
    return {"user_id": user.id, "username": user.username, "role": user.role, "ec_number": user.ec_number or "", "email": user.email or "", "display_name": user.display_name or ""}

@app.post("/auth/email/request")
async def email_request(payload: dict = Body(...)):
    email = (payload.get("email") or "").strip()
    if not email:
        raise HTTPException(status_code=400, detail="Email required")
    request_email_code(email)
    return {"message": "Verification code sent"}

@app.post("/auth/email/verify")
async def email_verify(payload: dict = Body(...), db: AsyncSession = Depends(get_db)):
    email = (payload.get("email") or "").strip()
    code = (payload.get("code") or "").strip()
    if not email or not code:
        raise HTTPException(status_code=400, detail="Email and code required")
    normalized = verify_email_code(email, code)
    provider = "email_otp"
    identity = normalized
    resprov = await db.execute(select(UserIdentityProvider).where(UserIdentityProvider.provider == provider, UserIdentityProvider.identity == identity))
    prov = resprov.scalar_one_or_none()
    user = None
    if prov:
        resu = await db.execute(select(User).where(User.id == prov.user_id))
        user = resu.scalar_one_or_none()
    if not user:
        resu = await db.execute(select(User).where((User.email == identity) | (User.username == identity)))
        user = resu.scalar_one_or_none()
    if not user:
        guess_ec = identity.split("@")[0] if "@" in identity else ""
        if guess_ec:
            resu = await db.execute(select(User).where((User.ec_number == guess_ec) | (User.username == guess_ec)))
            user = resu.scalar_one_or_none()
            if user and not user.email:
                user.email = identity
                db.add(user)
                await db.commit()
    if not user:
        display_name = identity.split("@")[0] if "@" in identity else identity
        user = User(username=identity, email=identity, display_name=display_name, role="analyst")
        db.add(user)
        await db.commit()
    if not user.email:
        user.email = identity
    if not user.display_name:
        user.display_name = (identity.split("@")[0] if "@" in identity else identity)
    db.add(user)
    await db.commit()

    resprov = await db.execute(select(UserIdentityProvider).where(UserIdentityProvider.provider == provider, UserIdentityProvider.identity == identity))
    prov = resprov.scalar_one_or_none()
    if not prov:
        prov = UserIdentityProvider(user_id=user.id, provider=provider, identity=identity, verified=True)
    prov.last_login_at = datetime.datetime.now(datetime.timezone.utc)
    prov.verified = True
    db.add(prov)
    await db.commit()

    token = create_session(user.id, user.display_name, provider, identity)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": user.id,
        "ec_number": user.ec_number or (user.email or ""),
        "email": user.email or "",
        "display_name": user.display_name or "",
        "role": user.role,
    }

@app.post("/admin/email/test")
async def admin_email_test(payload: dict = Body(None), user: User = Depends(get_current_user)):
    to = (payload or {}).get("to") or (f"{user.username}@{settings.allowed_email_domain}" if "@" not in user.username else user.username)
    host, port, usr, pw, use_tls = settings.smtp_host, settings.smtp_port, settings.smtp_user, settings.smtp_pass, settings.smtp_use_tls
    if not host or not usr or not pw:
        raise HTTPException(status_code=502, detail="SMTP not configured")
    msg = f"Subject: DocIntel Test\r\n\r\nThis is a DocIntel test message for {to}."
    try:
        if use_tls:
            context = ssl.create_default_context()
            with smtplib.SMTP(host, port, timeout=15) as server:
                server.starttls(context=context)
                server.login(usr, pw)
                server.sendmail(usr, [to], msg)
        else:
            with smtplib.SMTP(host, port, timeout=15) as server:
                server.login(usr, pw)
                server.sendmail(usr, [to], msg)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"SMTP error: {e}")
    return {"ok": True, "to": to}

@app.get("/users/me/summary-history")
async def summary_history(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DocAnalysis))
    rows = result.scalars().all()
    items = []
    for row in rows:
        items.append({
            "document_id": f"doc_{row.document_id}",
            "executive_summary": row.executive_summary or "",
            "detailed_summary": [p for p in (row.detailed_summary or "").split("\n") if p.strip()],
            "topics": (json.loads(row.topics_json) if row.topics_json else []),
            "entities": (json.loads(row.entities_json) if row.entities_json else []),
            "sentiment": row.sentiment or "Neutral",
            "action_items": (json.loads(row.action_items_json) if getattr(row, "action_items_json", None) else []),
            "decisions": (json.loads(row.decisions_json) if getattr(row, "decisions_json", None) else []),
            "created_at": "",  # SQLite default timestamp not tracked here; could extend schema
        })
    return {"ec_number": user.username, "history": items}

@app.get("/documents/{document_id}/analysis")
async def get_document_analysis_compat(document_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    doc_int = _parse_document_id(document_id)
    doc_res = await db.execute(select(DbDocument).where(DbDocument.id == doc_int))
    doc_row = doc_res.scalar_one_or_none()
    if not doc_row:
        raise HTTPException(status_code=404, detail="Document not found")
    await check_project_access(doc_row.project_id, user, db)
    await ensure_project_membership(doc_row.project_id, user, db, role_in_project="analyst")
    result = await db.execute(select(DocAnalysis).where(DocAnalysis.document_id == doc_int))
    row = result.scalar_one_or_none()
    if not row:
        status = doc_row.status
        return {
            "id": f"doc_{doc_int}",
            "executive_summary": "",
            "detailed_summary": [],
            "entities": [],
            "key_entities": {"people": [], "dates": [], "locations": []},
            "topics": [],
            "sentiment": "Neutral",
            "action_items": [],
            "decisions": [],
            "status": status.upper(),
        }
    return {
        "id": f"doc_{doc_int}",
        "executive_summary": row.executive_summary or "",
        "detailed_summary": [p for p in (row.detailed_summary or "").split("\n") if p.strip()],
        "entities": (json.loads(row.entities_json) if row.entities_json else []),
        "key_entities": {"people": [], "dates": [], "locations": []},
        "topics": (json.loads(row.topics_json) if row.topics_json else []),
        "sentiment": row.sentiment or "Neutral",
        "action_items": (json.loads(row.action_items_json) if getattr(row, "action_items_json", None) else []),
        "decisions": (json.loads(row.decisions_json) if getattr(row, "decisions_json", None) else []),
        "status": "READY",
    }

@app.get("/documents/{document_id}/prompts")
async def get_document_prompts_compat(document_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    doc_int = _parse_document_id(document_id)
    doc_res = await db.execute(select(DbDocument).where(DbDocument.id == doc_int))
    doc_row = doc_res.scalar_one_or_none()
    if not doc_row:
        raise HTTPException(status_code=404, detail="Document not found")
    await check_project_access(doc_row.project_id, user, db)
    await ensure_project_membership(doc_row.project_id, user, db, role_in_project="analyst")
    result = await db.execute(select(SuggestedPrompt).where(SuggestedPrompt.document_id == doc_int))
    rows = result.scalars().all()
    prompts = [r.prompt_text for r in rows][:5]
    if not prompts:
        prompts = [
            "Summarize this document in 10 sentences or less.",
            "List the key topics and entities mentioned in this document.",
            "List all action items and decisions mentioned in this document.",
            "Generate a process flow diagram (Mermaid) based on this document.",
            "What are the key requirements, deadlines, and responsibilities mentioned?",
        ]
    return {"document_id": f"doc_{doc_int}", "prompts": prompts}

@app.get("/api/prompts/suggest")
async def api_prompts_suggest(
    document_id: Optional[str] = None,
    project_id: Optional[int] = None,
    scope: str = "document",
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sc = (scope or "document").strip().lower()
    doc = None
    analysis = None
    resolved_project_id = None
    filename = ""
    if document_id:
        doc_int = _parse_document_id(document_id)
        dres = await db.execute(select(DbDocument).where(DbDocument.id == doc_int))
        doc = dres.scalar_one_or_none()
        if doc:
            resolved_project_id = int(doc.project_id)
            filename = doc.filename or ""
            await check_project_access(resolved_project_id, user, db)
            await ensure_project_membership(resolved_project_id, user, db, role_in_project="analyst")
            ares = await db.execute(select(DocAnalysis).where(DocAnalysis.document_id == doc_int))
            analysis = ares.scalar_one_or_none()
            sc = "document"
    if resolved_project_id is None and project_id is not None:
        resolved_project_id = int(project_id)
        await check_project_access(resolved_project_id, user, db)
        await ensure_project_membership(resolved_project_id, user, db, role_in_project="analyst")
        sc = "project"

    name_low = filename.lower()
    doc_kind = "document"
    if "net" in name_low and "meter" in name_low:
        doc_kind = "net-metering"
    elif "sop" in name_low:
        doc_kind = "sop"
    elif "minute" in name_low:
        doc_kind = "minutes"
    elif "policy" in name_low:
        doc_kind = "policy"

    doc_prompts = []
    if sc == "document":
        doc_prompts = [
            f"Summarize this {doc_kind} document in 10 bullets.",
            "List action items with owners and deadlines.",
            "Extract key entities (people, departments, locations, systems, dates).",
            "Extract risks, mitigations, and compliance implications.",
            "Generate a process flow diagram (Mermaid) for the main workflow described.",
        ]
        if analysis and (analysis.executive_summary or "").strip():
            doc_prompts.insert(0, "Give a 5-sentence executive summary, then 10 key takeaways.")

    cross = [
        "Which internal ZETDC policies or SOPs are relevant to this topic? Cite document IDs where possible.",
        "Compare this document’s requirements against ZETDC policy and highlight gaps.",
    ]

    diagrams = [
        "Draw a Mermaid flowchart showing the end-to-end process with decision points.",
        "Create a Mermaid sequence diagram of the main actors and steps.",
    ]

    spreadsheets = [
        "Propose 3 charts that could summarize the key numbers; specify x-axis and series.",
        "If this includes tables, suggest a bar chart and a trend line chart and what they show.",
    ]

    web_prompts = []
    if bool(getattr(settings, "zetdc", None) and getattr(settings.zetdc, "allow_web_search", False)):
        web_prompts = [
            "Find the latest regulator guidance relevant to this topic and summarize it with citations.",
        ]

    groups = [
        {"group": "Document", "prompts": doc_prompts[:6]},
        {"group": "Policy Cross-Refs", "prompts": cross},
        {"group": "Diagrams", "prompts": diagrams},
        {"group": "Spreadsheets/Charts", "prompts": spreadsheets},
    ]
    if web_prompts:
        groups.append({"group": "Web-Aware", "prompts": web_prompts})
    flat = []
    for g in groups:
        for p in g["prompts"]:
            if p and p not in flat:
                flat.append(p)
    return {"scope": sc, "groups": groups, "prompts": flat}

@app.post("/api/flowchart/suggest")
async def api_flowchart_suggest(payload: dict = Body(...), user: User = Depends(get_current_user)):
    text = (payload.get("text") or "").strip()
    if not text:
        return JSONResponse(status_code=400, content={"error": "missing_text"})
    from app.utils.ollama_client import ollama
    model = (payload.get("model") or settings.default_model or settings.text_model).strip()
    if not _is_generation_model(model):
        return JSONResponse(status_code=400, content={"error": "invalid_generation_model", "model": model})
    prompt = (
        "Return JSON with keys: diagram_types (array), steps (array of short steps), notes (string). "
        "Focus on a process flow that can be drawn."
        "\n\nTEXT:\n" + text
    )
    out = await ollama.generate(model, prompt, system=(settings.zetdc.system_prompt or None))
    return {"suggestion": out}

@app.post("/api/flowcharts/suggest")
async def api_flowcharts_suggest(payload: dict = Body(...), user: User = Depends(get_current_user)):
    return await api_flowchart_suggest(payload=payload, user=user)

@app.post("/api/flowchart/generate")
async def api_flowchart_generate(payload: dict = Body(...), user: User = Depends(get_current_user)):
    text = (payload.get("text") or "").strip()
    diagram_type = (payload.get("diagram_type") or "flowchart").strip().lower()
    if not text:
        return JSONResponse(status_code=400, content={"error": "missing_text"})
    from app.utils.ollama_client import ollama
    model = (payload.get("model") or settings.default_model or settings.text_model).strip()
    if not _is_generation_model(model):
        return JSONResponse(status_code=400, content={"error": "invalid_generation_model", "model": model})
    prompt = (
        "Generate a Mermaid diagram. Return only a Mermaid code block (no extra commentary). "
        f"Diagram type: {diagram_type}."
        "\n\nTEXT:\n" + text
    )
    mermaid = await ollama.generate(model, prompt, system=(settings.zetdc.system_prompt or None))
    return {"mermaid": mermaid, "drawing_prompt": f"{diagram_type} for described process"}

@app.post("/api/flowcharts/generate")
async def api_flowcharts_generate(payload: dict = Body(...), user: User = Depends(get_current_user)):
    return await api_flowchart_generate(payload=payload, user=user)

@app.post("/api/charts/analyze")
async def api_charts_analyze(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
):
    name = (file.filename or "").lower()
    if not (name.endswith(".csv") or (file.content_type or "").lower().endswith("csv")):
        return JSONResponse(status_code=400, content={"error": "unsupported_file", "supported": ["csv"]})
    import csv
    raw = await file.read()
    text = raw.decode("utf-8", errors="ignore")
    reader = csv.DictReader(text.splitlines())
    rows = []
    for i, r in enumerate(reader):
        if i >= 200:
            break
        rows.append(r)
    cols = reader.fieldnames or []
    numeric = set()
    for c in cols:
        ok = 0
        total = 0
        for r in rows[:50]:
            v = (r.get(c) or "").strip()
            if not v:
                continue
            total += 1
            try:
                float(v.replace(",", ""))
                ok += 1
            except Exception:
                pass
        if total > 0 and ok / total >= 0.8:
            numeric.add(c)
    suggestions = []
    if cols:
        non_num = [c for c in cols if c not in numeric]
        num = [c for c in cols if c in numeric]
        if non_num and num:
            suggestions.append({"chart_type": "bar", "x": non_num[0], "y": [num[0]]})
        if len(num) >= 2:
            suggestions.append({"chart_type": "line", "x": cols[0], "y": num[:2]})
    return {"columns": cols, "numeric_columns": sorted(list(numeric)), "suggestions": suggestions}

def _draw_basic_chart(
    *,
    chart_type: str,
    x_labels: list[str],
    series: list[tuple[str, list[float]]],
    title: str,
    width: int = 900,
    height: int = 520,
) -> bytes:
    import io
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (width, height), (255, 255, 255))
    d = ImageDraw.Draw(img)
    pad = 60
    plot_w = width - pad * 2
    plot_h = height - pad * 2
    d.text((pad, 18), title or "Chart", fill=(20, 20, 20))
    d.rectangle((pad, pad, pad + plot_w, pad + plot_h), outline=(200, 200, 200), width=1)

    if not x_labels or not series:
        out = io.BytesIO()
        img.save(out, format="PNG")
        return out.getvalue()

    all_vals = []
    for _, vals in series:
        all_vals.extend([v for v in vals if isinstance(v, (int, float))])
    vmin = min(all_vals) if all_vals else 0.0
    vmax = max(all_vals) if all_vals else 1.0
    if vmax == vmin:
        vmax = vmin + 1.0

    def x_pos(i: int) -> int:
        if len(x_labels) <= 1:
            return pad
        return pad + int((i / (len(x_labels) - 1)) * plot_w)

    def y_pos(v: float) -> int:
        t = (v - vmin) / (vmax - vmin)
        return pad + plot_h - int(t * plot_h)

    palette = [(26, 115, 232), (234, 67, 53), (52, 168, 83), (251, 188, 5)]

    if chart_type == "bar":
        name, vals = series[0]
        n = len(x_labels)
        bar_w = max(4, int(plot_w / max(1, n) * 0.6))
        for i, lab in enumerate(x_labels):
            v = vals[i] if i < len(vals) else 0.0
            x = x_pos(i)
            left = x - bar_w // 2
            top = y_pos(float(v))
            d.rectangle((left, top, left + bar_w, pad + plot_h), fill=palette[0], outline=None)
            if i < 18:
                d.text((max(pad, left), pad + plot_h + 6), str(lab)[:12], fill=(80, 80, 80))
        d.text((pad, pad - 28), name, fill=palette[0])
    else:
        for si, (name, vals) in enumerate(series):
            color = palette[si % len(palette)]
            pts = []
            for i, lab in enumerate(x_labels):
                v = vals[i] if i < len(vals) else 0.0
                pts.append((x_pos(i), y_pos(float(v))))
            for i in range(1, len(pts)):
                d.line((pts[i - 1][0], pts[i - 1][1], pts[i][0], pts[i][1]), fill=color, width=3)
            for p in pts[:60]:
                d.ellipse((p[0] - 3, p[1] - 3, p[0] + 3, p[1] + 3), fill=color)
            d.text((pad + 10 + si * 160, pad - 28), name[:18], fill=color)
        for i, lab in enumerate(x_labels[:18]):
            d.text((x_pos(i), pad + plot_h + 6), str(lab)[:10], fill=(80, 80, 80))

    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()

@app.post("/api/charts/build")
async def api_charts_build(payload: dict = Body(...), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    import io
    session_id = (payload.get("session_id") or "").strip()
    chart_type = (payload.get("chart_type") or "line").strip().lower()
    title = (payload.get("title") or "").strip()
    x = payload.get("x")
    y = payload.get("y")
    data = payload.get("data")
    if not session_id:
        return JSONResponse(status_code=400, content={"error": "missing_session_id"})
    sres = await db.execute(select(DbSession).where(DbSession.session_uuid == session_id))
    sess = sres.scalar_one_or_none()
    if not sess or (sess.user_id != user.id and user.role != "admin"):
        return JSONResponse(status_code=403, content={"error": "access_denied"})
    if not isinstance(data, list) or not isinstance(x, str) or not isinstance(y, list) or not y:
        return JSONResponse(status_code=400, content={"error": "invalid_payload"})

    x_labels: list[str] = []
    series: list[tuple[str, list[float]]] = []
    for row in data:
        if not isinstance(row, dict):
            continue
        x_labels.append(str(row.get(x, "")))
    for col in y:
        if not isinstance(col, str):
            continue
        vals: list[float] = []
        for row in data:
            if not isinstance(row, dict):
                vals.append(0.0)
                continue
            v = row.get(col, 0)
            try:
                vals.append(float(str(v).replace(",", "")))
            except Exception:
                vals.append(0.0)
        series.append((col, vals))

    png = _draw_basic_chart(chart_type=chart_type, x_labels=x_labels, series=series[:3], title=title or f"{chart_type} chart")
    out_dir = Path(settings.base_dir) / "data" / "charts" / session_id
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"chart_{ts}.png"
    out_path = out_dir / filename
    out_path.write_bytes(png)
    return {"ok": True, "url": f"/api/charts/{session_id}/{filename}", "path": str(out_path)}

@app.get("/api/charts/{session_id}/{filename}")
async def api_charts_file(session_id: str, filename: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    sres = await db.execute(select(DbSession).where(DbSession.session_uuid == session_id))
    sess = sres.scalar_one_or_none()
    if not sess or (sess.user_id != user.id and user.role != "admin"):
        raise HTTPException(status_code=403, detail="Access denied")
    safe_sid = re.sub(r"[^a-zA-Z0-9_\\-]", "", session_id)
    safe_fn = re.sub(r"[^a-zA-Z0-9_\\-\\.]", "", filename)
    p = Path(settings.base_dir) / "data" / "charts" / safe_sid / safe_fn
    if not p.exists():
        raise HTTPException(status_code=404, detail="Chart not found")
    return FileResponse(str(p))

@app.get("/admin/models/active")
async def admin_models_active():
    return model_active()

@app.post("/admin/models/select")
async def admin_models_select(payload: dict = Body(...)):
    model = payload.get("model")
    model_force(model)
    return {"selected": model}

def _deep_get_value(d: dict, path: str):
    cur = d
    for p in (path or "").split("."):
        if not isinstance(cur, dict) or p not in cur:
            return None
        cur = cur[p]
    return cur

@app.get("/admin/settings")
async def admin_settings_get(user: User = Depends(require_role(["admin"])), db: AsyncSession = Depends(get_db)):
    effective, sources = await get_effective_settings(db)
    return {"effective": effective, "sources": sources}

@app.patch("/admin/settings")
async def admin_settings_patch(payload: dict = Body(...), user: User = Depends(require_role(["admin"])), db: AsyncSession = Depends(get_db)):
    try:
        patch_flat = await validate_settings_payload(db, payload or {})
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": "invalid_settings", "detail": str(e)})
    effective_before, _ = await get_effective_settings(db)

    changed_keys = list(patch_flat.keys())
    for key, value in patch_flat.items():
        old_value = _deep_get_value(effective_before, key)
        res = await db.execute(select(SystemSetting).where(SystemSetting.key == key))
        row = res.scalar_one_or_none()
        if not row:
            row = SystemSetting(key=key, value_json=json.dumps(value), updated_by_user_id=user.id)
        else:
            row.value_json = json.dumps(value)
            row.updated_by_user_id = user.id
        db.add(row)
        db.add(
            SettingsAudit(
                key=key,
                old_value_json=json.dumps(old_value),
                new_value_json=json.dumps(value),
                changed_by_user_id=user.id,
            )
        )
    await db.commit()

    effective_after, sources = await get_effective_settings(db)
    apply_live_settings(effective_after)
    restart_map = restart_recommended_for_keys(changed_keys)
    return {"ok": True, "restart_recommended": restart_map, "effective": effective_after, "sources": sources}

@app.post("/admin/settings/test")
async def admin_settings_test(payload: dict = Body(...), user: User = Depends(require_role(["admin"])), db: AsyncSession = Depends(get_db)):
    try:
        patch_flat = await validate_settings_payload(db, payload or {})
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": "invalid_settings", "detail": str(e)})
    restart_map = restart_recommended_for_keys(list(patch_flat.keys()))
    return {"ok": True, "restart_recommended": restart_map}

@app.post("/admin/settings/backup")
async def admin_settings_backup(user: User = Depends(require_role(["admin"])), db: AsyncSession = Depends(get_db)):
    effective, _ = await get_effective_settings(db)
    out_dir = Path(settings.base_dir) / "backups" / "settings"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"{ts}.yaml"
    with open(out_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(effective, f, sort_keys=False)
    return {"ok": True, "path": str(out_path)}

@app.post("/admin/settings/restore")
async def admin_settings_restore(payload: dict = Body(...), user: User = Depends(require_role(["admin"])), db: AsyncSession = Depends(get_db)):
    path = (payload.get("path") or "").strip()
    raw_yaml = payload.get("yaml")
    data = None
    if path:
        p = Path(path)
        if not p.exists():
            return JSONResponse(status_code=404, content={"error": "file_missing"})
        with open(p, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    elif isinstance(raw_yaml, str) and raw_yaml.strip():
        data = yaml.safe_load(raw_yaml) or {}
    else:
        return JSONResponse(status_code=400, content={"error": "missing_restore_input"})

    try:
        patch_flat = await validate_settings_payload(db, data or {})
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": "invalid_settings", "detail": str(e)})
    effective_before, _ = await get_effective_settings(db)
    changed_keys = list(patch_flat.keys())
    for key, value in patch_flat.items():
        old_value = _deep_get_value(effective_before, key)
        res = await db.execute(select(SystemSetting).where(SystemSetting.key == key))
        row = res.scalar_one_or_none()
        if not row:
            row = SystemSetting(key=key, value_json=json.dumps(value), updated_by_user_id=user.id)
        else:
            row.value_json = json.dumps(value)
            row.updated_by_user_id = user.id
        db.add(row)
        db.add(
            SettingsAudit(
                key=key,
                old_value_json=json.dumps(old_value),
                new_value_json=json.dumps(value),
                changed_by_user_id=user.id,
            )
        )
    await db.commit()

    effective_after, sources = await get_effective_settings(db)
    apply_live_settings(effective_after)
    restart_map = restart_recommended_for_keys(changed_keys)
    return {"ok": True, "restart_recommended": restart_map, "effective": effective_after, "sources": sources}

@app.get("/admin/settings/audit")
async def admin_settings_audit(
    limit: int = 100,
    key: Optional[str] = None,
    user: User = Depends(require_role(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    lim = max(1, min(500, int(limit)))
    q = select(SettingsAudit).order_by(SettingsAudit.changed_at.desc()).limit(lim)
    if key:
        q = select(SettingsAudit).where(SettingsAudit.key == key).order_by(SettingsAudit.changed_at.desc()).limit(lim)
    res = await db.execute(q)
    rows = list(res.scalars().all())
    items = []
    for r in rows:
        items.append(
            {
                "id": r.id,
                "key": r.key,
                "old_value": r.old_value_json,
                "new_value": r.new_value_json,
                "changed_by_user_id": r.changed_by_user_id,
                "changed_at": str(r.changed_at) if r.changed_at else "",
            }
        )
    return {"audit": items}

@app.post("/admin/reset/hard")
async def admin_reset_hard(payload: dict = Body(...), user: User = Depends(require_role(["admin"])), db: AsyncSession = Depends(get_db)):
    token = (payload.get("confirm_token") or "").strip()
    drop_users = bool(payload.get("drop_users", False))
    if token != "RESET_DOCTEL":
        return JSONResponse(status_code=400, content={"error": "confirm_token_required", "expected": "RESET_DOCTEL"})

    base_dir = Path(settings.base_dir)
    db_path = base_dir / "db" / "app.db"
    chroma_path = Path(settings.chroma_path)

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    db_backup_dir = base_dir / "backups" / "db"
    chroma_backup_dir = base_dir / "backups" / "chroma"
    db_backup_dir.mkdir(parents=True, exist_ok=True)
    chroma_backup_dir.mkdir(parents=True, exist_ok=True)

    if db_path.exists():
        shutil.copy2(str(db_path), str(db_backup_dir / f"app_{ts}.db"))
    if chroma_path.exists():
        dst = chroma_backup_dir / f"chroma_{ts}"
        if dst.exists():
            shutil.rmtree(dst, ignore_errors=True)
        shutil.copytree(str(chroma_path), str(dst))

    await db.execute(delete(DbMessage))
    await db.execute(delete(DbSession))
    await db.execute(delete(Chunk))
    await db.execute(delete(Embedding))
    await db.execute(delete(SuggestedPrompt))
    await db.execute(delete(DocAnalysis))
    await db.execute(delete(DbDocument))
    await db.execute(delete(DocumentLink))
    await db.execute(delete(Diagram))
    await db.execute(delete(ProjectMember))
    await db.execute(delete(Project))
    if drop_users:
        await db.execute(delete(UserIdentityProvider))
        await db.execute(delete(User))
    await db.commit()

    try:
        if chroma_path.exists():
            shutil.rmtree(chroma_path, ignore_errors=True)
        chroma_path.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

    res = await db.execute(select(SystemSetting).where(SystemSetting.key == "bootstrap_required"))
    row = res.scalar_one_or_none()
    if not row:
        row = SystemSetting(key="bootstrap_required", value_json=json.dumps(True), updated_by_user_id=user.id)
    else:
        row.value_json = json.dumps(True)
        row.updated_by_user_id = user.id
    db.add(row)
    await db.commit()

    asyncio.create_task(run_bootstrap_scan())
    return {"ok": True, "db_backup": str(db_backup_dir / f"app_{ts}.db"), "chroma_backup": str(chroma_backup_dir / f"chroma_{ts}")}

@app.get("/api/logs/tail")
async def logs_tail(lines: int = 200, user: User = Depends(require_role(["admin"]))):
    log_path = settings.projects_dir.parent.parent / "logs" / "app.log"
    if not log_path.exists():
        return {"lines": []}
    n = max(1, min(1000, int(lines)))
    with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
        data = f.readlines()
    return {"lines": data[-n:]}

if __name__ == "__main__":
    uvicorn.run("app.main:app", host=settings.bind_host, port=settings.port, reload=True)
