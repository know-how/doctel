"""
DocTel charts router.

Endpoints for flowchart suggestions/generation and chart analysis/build.
"""

import csv
import io

from pathlib import Path

from app.routers.deps import (
    Body,
    Depends,
    File,
    FileResponse,
    HTTPException,
    JSONResponse,
    Query,
    UploadFile,
    User,
    DbSession,
    AsyncSession,
    get_db,
    get_current_user,
    settings,
    ollama,
    re,
    datetime,
    select,
    _is_generation_model,
    _draw_basic_chart,
    logger,
)

from fastapi import APIRouter

router = APIRouter(tags=["charts"])


# ── Flowchart suggest ────────────────────────────────────────────────────────


async def _flowchart_suggest(text: str, model: str = "", db: AsyncSession = None) -> dict:
    """Core implementation for flowchart suggestion."""
    if not text:
        return JSONResponse(status_code=400, content={"error": "missing_text"})
    
    # Use centralized model resolver
    from app.services.model_resolver_service import resolve_model
    if db:
        resolved = await resolve_model(db, requested_model=model, task_type="chat")
        mdl = resolved["model_id"]
    else:
        # Fallback for backward compatibility
        mdl = (model or settings.default_model or settings.text_model).strip()
    
    if not _is_generation_model(mdl):
        return JSONResponse(status_code=400, content={"error": "invalid_generation_model", "model": mdl})
    prompt = (
        "Return JSON with keys: diagram_types (array), steps (array of short steps), notes (string). "
        "Focus on a process flow that can be drawn."
        "\n\nTEXT:\n" + text
    )
    out = await ollama.generate(mdl, prompt, system=(settings.zetdc.system_prompt or None))
    return {"suggestion": out}


@router.post("/api/flowchart/suggest")
async def api_flowchart_suggest(
    payload: dict = Body(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _flowchart_suggest(
        text=(payload.get("text") or "").strip(),
        model=(payload.get("model") or "").strip(),
        db=db,
    )


@router.post("/api/flowcharts/suggest")
async def api_flowcharts_suggest(
    payload: dict = Body(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _flowchart_suggest(
        text=(payload.get("text") or "").strip(),
        model=(payload.get("model") or "").strip(),
        db=db,
    )


# ── Flowchart generate ───────────────────────────────────────────────────────


async def _flowchart_generate(
    text: str, 
    diagram_type: str = "flowchart", 
    model: str = "",
    db: AsyncSession = None
) -> dict:
    """Core implementation for flowchart generation."""
    if not text:
        return JSONResponse(status_code=400, content={"error": "missing_text"})
    dt = (diagram_type or "flowchart").strip().lower()
    
    # Use centralized model resolver
    from app.services.model_resolver_service import resolve_model
    if db:
        resolved = await resolve_model(db, requested_model=model, task_type="chat")
        mdl = resolved["model_id"]
    else:
        # Fallback for backward compatibility
        mdl = (model or settings.default_model or settings.text_model).strip()
    
    if not _is_generation_model(mdl):
        return JSONResponse(status_code=400, content={"error": "invalid_generation_model", "model": mdl})
    prompt = (
        "Generate a Mermaid diagram. Return only a Mermaid code block (no extra commentary). "
        f"Diagram type: {dt}."
        "\n\nTEXT:\n" + text
    )
    mermaid = await ollama.generate(mdl, prompt, system=(settings.zetdc.system_prompt or None))
    return {"mermaid": mermaid, "drawing_prompt": f"{dt} for described process"}


@router.post("/api/flowchart/generate")
async def api_flowchart_generate(
    payload: dict = Body(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _flowchart_generate(
        text=(payload.get("text") or "").strip(),
        diagram_type=(payload.get("diagram_type") or "flowchart").strip(),
        model=(payload.get("model") or "").strip(),
        db=db,
    )


@router.post("/api/flowcharts/generate")
async def api_flowcharts_generate(
    payload: dict = Body(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _flowchart_generate(
        text=(payload.get("text") or "").strip(),
        diagram_type=(payload.get("diagram_type") or "flowchart").strip(),
        model=(payload.get("model") or "").strip(),
        db=db,
    )


# ── Chart analysis ───────────────────────────────────────────────────────────


@router.post("/api/charts/analyze")
async def api_charts_analyze(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
):
    name = (file.filename or "").lower()
    if not (name.endswith(".csv") or (file.content_type or "").lower().endswith("csv")):
        return JSONResponse(status_code=400, content={"error": "unsupported_file", "supported": ["csv"]})
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


# ── Chart build ──────────────────────────────────────────────────────────────


@router.post("/api/charts/build")
async def api_charts_build(
    payload: dict = Body(...),
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
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

    png = _draw_basic_chart(
        chart_type=chart_type,
        x_labels=x_labels,
        series=series[:3],
        title=title or f"{chart_type} chart",
    )
    out_dir = Path(settings.base_dir) / "data" / "charts" / session_id
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"chart_{ts}.png"
    out_path = out_dir / filename
    out_path.write_bytes(png)
    return {"ok": True, "url": f"/api/charts/{session_id}/{filename}", "path": str(out_path)}


# ── Chart file serving ───────────────────────────────────────────────────────


@router.get("/api/charts/{session_id}/{filename}")
async def api_charts_file(
    session_id: str,
    filename: str,
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
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
