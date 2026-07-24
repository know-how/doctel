"""
DocTel shared router dependencies.

Centralises imports, helpers, and globals that are used across multiple
router modules so each router file stays lean and imports are consistent.
"""

# ---------------------------------------------------------------------------
# Standard library
# ---------------------------------------------------------------------------
import asyncio
import datetime
import io
import json
import uuid
import logging
import os
import re
import shutil
from typing import Optional, Any, List

# ---------------------------------------------------------------------------
# FastAPI / Starlette
# ---------------------------------------------------------------------------
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Body, Query
from fastapi import Request
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse

# ---------------------------------------------------------------------------
# SQLAlchemy
# ---------------------------------------------------------------------------
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete, update, and_, or_, text

# ---------------------------------------------------------------------------
# App config & database
# ---------------------------------------------------------------------------
from app.config import settings
from app.db.database import get_db, AsyncSessionLocal

# ---------------------------------------------------------------------------
# Database models
# ---------------------------------------------------------------------------
from app.db.models import (
    Project,
    Document,
    User,
    DocAnalysis,
    SuggestedPrompt,
    ProjectMember,
    Session as DbSession,
    Diagram,
    Chunk,
    Embedding,
    UserIdentityProvider,
    DocumentLink,
    SystemSetting,
    SettingsAudit,
    SystemPrompt,
    Message as DbMessage,
)
from app.db.models import Document as DbDocument
from app.db.enterprise_models import (
    DocAnalysisVersion,
    QuotationSpan,
    KnowledgeNode,
    KnowledgeEdge,
    DocumentVersion,
    Agent,
    AgentExecution,
    HumanReview,
    PromptTemplate,
    PromptTemplateVersion,
    BenchmarkRun,
    BenchmarkResult,
    CostRecord,
    BudgetAlert,
    ConfidenceScore,
    DepartmentRestriction,
    InteractionAudit,
)

# ---------------------------------------------------------------------------
# Security / RBAC
# ---------------------------------------------------------------------------
from app.security.rbac import get_current_user, require_role, check_project_access, ensure_project_membership

# ---------------------------------------------------------------------------
# Pydantic schemas (from app.models)
# ---------------------------------------------------------------------------
from app.models import (
    AskResponse,
    UploadResponse,
    UploadedDocument,
    ProjectsListResponse,
    ProjectInfo,
    HealthResponse,
    ModelsAvailableResponse,
    ModelLabelsResponse,
    BasicResponse,
    Citation,
    CrossReference,
    ChatRequest,
    ChatResponse,
    ChatSource,
    DocumentCreateResponse,
    DocumentAnalysisResponse,
    PromptListResponse,
    ProjectCreateRequest,
    ProjectSummary,
    ProjectResponse,
    ProjectListResponse,
    ProjectDocumentListResponse,
    LoginRequest,
    LoginResponse,
    EmailOtpRequest,
    EmailOtpVerifyRequest,
    EmailOtpRequestResponse,
    SummaryHistoryEntry,
    SummaryHistoryResponse,
    OllamaModelDetail,
    DocumentMetadata,
)

# ---------------------------------------------------------------------------
# Service imports – cloud model services (often used inline, but lifted here)
# ---------------------------------------------------------------------------
from app.services.ingestion_service import ingest_document, get_file_hash
from app.services.rag_service import get_rag_answer, get_rag_answer_scoped
from app.services.document_response_service import generate_document_response
from app.services.vision_service import analyze_image
from app.services.auth_service import (
    verify_ad_credentials,
    request_email_code,
    verify_email_code,
    create_session,
    revoke_token,
)
from app.services.model_router import (
    active as model_active,
    force_select as model_force,
    select_model_with_fallback,
    force_select,
)
from app.services.job_poller import create_job as enqueue_ingest, cancel_job
from app.utils.model_cache import load_model_cache, update_installed_models, set_pull_state
from app.services.bootstrap_service import run_bootstrap_scan, start_watcher, get_bootstrap_status
from app.services.system_settings_service import (
    get_effective_settings,
    validate_settings_payload,
    apply_live_settings,
    restart_recommended_for_keys,
)
from app.services import auth_service

# ---------------------------------------------------------------------------
# Utils
# ---------------------------------------------------------------------------
from app.utils.ollama_client import ollama

# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared globals – ask inflight guard & metrics
# ---------------------------------------------------------------------------
_ask_inflight: dict[str, float] = {}
_ask_lock = asyncio.Lock()
_metrics: dict[str, int] = {"uploads_total": 0, "ingest_total": 0}

# ---------------------------------------------------------------------------
# SSE globals – cross‑platform sync (logout, training, etc.)
# ---------------------------------------------------------------------------
_sse_clients: set[asyncio.Queue] = set()
# Per-user poll buffer: each user only sees events they triggered
_sse_poll_buffers: dict[str, list[dict]] = {}
_sse_poll_lock = asyncio.Lock()


# ---------------------------------------------------------------------------
# SSE helpers
# ---------------------------------------------------------------------------
async def _sse_broadcast(event_type: str, data: dict) -> None:
    """Push an event to all connected SSE clients and per-user poll buffer."""
    payload = json.dumps({"event": event_type, "data": data})
    dead = set()
    for q in _sse_clients:
        try:
            q.put_nowait(payload)
        except asyncio.QueueFull:
            dead.add(q)
    _sse_clients.difference_update(dead)
    # Store in per-user poll buffer so other users don't receive this event
    user_id = str(data.get("user_id", "")) if data else ""
    if user_id:
        async with _sse_poll_lock:
            if user_id not in _sse_poll_buffers:
                _sse_poll_buffers[user_id] = []
            _sse_poll_buffers[user_id].append({"event": event_type, "data": data})
            if len(_sse_poll_buffers[user_id]) > 50:
                _sse_poll_buffers[user_id][:25] = []


async def _sse_generator(queue: asyncio.Queue):
    """Async generator that yields SSE-formatted events."""
    try:
        yield "data: {\"event\": \"connected\"}\n\n"
        while True:
            try:
                payload = await asyncio.wait_for(queue.get(), timeout=25.0)
                yield f"data: {payload}\n\n"
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"
    except asyncio.CancelledError:
        pass
    finally:
        _sse_clients.discard(queue)


# ---------------------------------------------------------------------------
# Shared helper functions extracted from main.py
# ---------------------------------------------------------------------------

def _parse_document_id(document_id: str) -> str:
    """Parse a document id string (e.g. 'doc_<uuid>') into a plain UUID string.

    Accepts:
      - Raw UUID strings: "550e8400-e29b-41d4-a716-446655440000"
      - Prefixed UUID strings: "doc_550e8400-e29b-41d4-a716-446655440000"
      - Legacy integer strings: "42" (for backward compat with old routes)
    Returns the plain identifier as a string.
    Raises HTTPException(400) if the input is empty or clearly invalid.
    """
    if isinstance(document_id, str):
        doc_str = document_id.strip()
        if not doc_str:
            raise HTTPException(status_code=400, detail="Empty document id")
        # Strip legacy "doc_" prefix
        match = re.match(r"^doc_(.+)$", doc_str)
        if match:
            return match.group(1)
        return doc_str
    return str(document_id)


def _is_embedding_model(model: str) -> bool:
    """Return True if the model name looks like an embedding model."""
    lowered = model.lower()
    return any(kw in lowered for kw in ["embed", "bge", "e5-", "mxbai"])


def _is_generation_model(model: str) -> bool:
    """Return True if the model name looks like a text generation model."""
    lowered = model.lower()
    return not _is_embedding_model(model) and any(
        kw in lowered for kw in ["llama", "mistral", "qwen", "gemma", "phi", "deepseek", "gpt", "gemini", "cloud"]
    )


def _derive_session_title(text: str, fallback: str = "Conversation") -> str:
    """Derive a short session title from the first user message."""
    t = (text or "").strip()
    if not t:
        return fallback
    MAX_TITLE_LEN = 120
    if len(t) <= MAX_TITLE_LEN:
        return t
    return t[: MAX_TITLE_LEN - 3] + "..."


async def _accessible_project_ids(user: User, db: AsyncSession) -> list[int]:
    """Return list of project ids the user can access (admin → all, others → membership)."""
    if user.role == "admin":
        res = await db.execute(select(Project.id))
        return [row[0] for row in res.all()]
    res = await db.execute(select(ProjectMember.project_id).where(ProjectMember.user_id == user.id))
    return [row[0] for row in res.all()]


async def _searchable_project_ids(db: AsyncSession) -> list[int]:
    """Return list of all non‑archived project ids (for global search)."""
    res = await db.execute(select(Project.id).where(Project.archived_at.is_(None)))
    return [row[0] for row in res.all()]


async def _can_view_document(doc: DbDocument, user: User, db: AsyncSession) -> bool:
    """Check whether the user is allowed to view a document."""
    if user.role == "admin":
        return True
    if doc.project_id is None:
        return False
    res = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == doc.project_id,
            ProjectMember.user_id == user.id,
        )
    )
    return res.scalar_one_or_none() is not None


async def _assert_document_workspace_access(doc: DbDocument, user: User, db: AsyncSession) -> None:
    """Raise 403 if the user cannot access the given document."""
    if not await _can_view_document(doc, user, db):
        raise HTTPException(status_code=403, detail="Access denied to document")


def _deep_get_value(d: dict, path: str):
    """Retrieve a nested value from a dict using a dot‑separated path."""
    cur = d
    for p in (path or "").split("."):
        if not isinstance(cur, dict) or p not in cur:
            return None
        cur = cur[p]
    return cur


# ---------------------------------------------------------------------------
# Chart drawing helper (PIL‑based, used by charts router)
# ---------------------------------------------------------------------------
def _draw_basic_chart(
    chart_type: str,
    x_labels: list[str],
    series: list[tuple[str, list[float]]],
    title: str = "",
    width: int = 800,
    height: int = 480,
) -> bytes:
    """Draw a simple bar or line chart with PIL and return PNG bytes."""
    from PIL import Image, ImageDraw, ImageFont

    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "C:\\Windows\\Fonts\\arial.ttf",
    ]
    font = None
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                font = ImageFont.truetype(fp, 12)
            except Exception:
                continue
            break
    if font is None:
        font = ImageFont.load_default()

    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)

    margin = {"l": 60, "r": 20, "t": 40, "b": 60}
    plot_w = width - margin["l"] - margin["r"]
    plot_h = height - margin["t"] - margin["b"]

    # Collect all values for Y-axis scaling
    all_vals = []
    for _, vals in series:
        all_vals.extend(vals)
    if not all_vals:
        all_vals = [0, 1]
    y_min = min(all_vals)
    y_max = max(all_vals)
    if abs(y_max - y_min) < 1e-9:
        y_max = y_min + 1.0

    palette = ["#4e79a7", "#f28e2b", "#e15759", "#76b7b2", "#59a14f", "#edc948"]
    n_series = len(series)
    n_x = len(x_labels)

    if chart_type == "bar":
        group_w = plot_w / max(n_x, 1)
        bar_w = group_w / max(n_series, 1) * 0.7
        for si, (label, vals) in enumerate(series):
            color = palette[si % len(palette)]
            for xi in range(min(n_x, len(vals))):
                x0 = margin["l"] + xi * group_w + si * bar_w + (group_w - n_series * bar_w) / 2
                v = vals[xi]
                h = ((v - y_min) / (y_max - y_min)) * plot_h
                y0 = margin["t"] + plot_h - h
                draw.rectangle([x0, y0, x0 + bar_w - 1, margin["t"] + plot_h], fill=color)
        # X-axis labels
        for xi in range(n_x):
            cx = margin["l"] + xi * group_w + group_w / 2
            draw.text((cx, height - margin["b"] + 4), str(x_labels[xi]), fill="black", font=font, anchor="mt")
    else:  # line chart
        for si, (label, vals) in enumerate(series):
            color = palette[si % len(palette)]
            pts = []
            for xi in range(min(n_x, len(vals))):
                x = margin["l"] + (xi / max(n_x - 1, 1)) * plot_w
                v = vals[xi]
                y = margin["t"] + plot_h - ((v - y_min) / (y_max - y_min)) * plot_h
                pts.append((x, y))
            if len(pts) > 1:
                draw.line(pts, fill=color, width=2)
            for x, y in pts:
                draw.ellipse([x - 3, y - 3, x + 3, y + 3], fill=color)
        for xi in range(n_x):
            x = margin["l"] + (xi / max(n_x - 1, 1)) * plot_w
            draw.text((x, height - margin["b"] + 4), str(x_labels[xi]), fill="black", font=font, anchor="mt")

    # Y-axis labels
    for yi in range(5):
        frac = yi / 4.0
        y = margin["t"] + plot_h - frac * plot_h
        val = y_min + frac * (y_max - y_min)
        draw.text((margin["l"] - 6, y), f"{val:.1f}", fill="black", font=font, anchor="rm")

    # Title
    if title:
        draw.text((width / 2, 12), title, fill="black", font=font, anchor="mt")

    # Legend
    legend_y = height - 16
    x_offset = margin["l"]
    for si, (label, _) in enumerate(series):
        color = palette[si % len(palette)]
        draw.rectangle([x_offset, legend_y - 4, x_offset + 12, legend_y + 4], fill=color)
        draw.text((x_offset + 16, legend_y), label[:30], fill="black", font=font, anchor="lm")
        x_offset += 16 + draw.textlength(label[:30], font=font) + 16

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
