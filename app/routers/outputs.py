"""
DocTel outputs router.

Endpoints for listing analysis outputs and exporting them.
"""

from fastapi import APIRouter

from app.routers.deps import (
    Depends,
    Optional,
    User,
    AsyncSession,
    get_db,
    get_current_user,
    HTTPException,
    json,
    JSONResponse,
    select,
    Document,
    DocAnalysis,
)

router = APIRouter(tags=["outputs"])


# ─────────────────────────────────────────────────────────────────────────────
# Outputs API
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/api/outputs")
async def get_outputs(
    type: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    lim = max(1, min(200, page_size))
    offset = max(0, (page - 1)) * lim
    q = select(DocAnalysis)
    if type:
        q = q.order_by(DocAnalysis.id.desc()).offset(offset).limit(lim)
    else:
        q = q.order_by(DocAnalysis.id.desc()).offset(offset).limit(lim)
    res = await db.execute(q)
    analyses = list(res.scalars().all())
    outputs = []
    for a in analyses:
        doc_res = await db.execute(select(Document).where(Document.id == a.document_id))
        d = doc_res.scalar_one_or_none()
        fname = d.filename if d else "Unknown"
        pid = str(d.project_id) if d and d.project_id else None
        outputs.append({
            "id": f"out_{a.id}",
            "document_id": f"doc_{a.document_id}",
            "filename": fname,
            "project_id": pid,
            "type": "analysis",
            "created_at": str(getattr(d, "created_at", "")) if d else "",
        })
    return {"outputs": outputs, "total": len(outputs), "page": page, "page_size": lim}


@router.get("/api/outputs/{output_id}/export")
async def export_output(
    output_id: str,
    format: str = "json",
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    clean = output_id.replace("out_", "")
    try:
        a_int = int(clean)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid output ID")
    res = await db.execute(select(DocAnalysis).where(DocAnalysis.id == a_int))
    analysis = res.scalar_one_or_none()
    if not analysis:
        raise HTTPException(status_code=404, detail="Output not found")
    data = {
        "executive_summary": analysis.executive_summary or "",
        "detailed_summary": json.loads(analysis.detailed_summary) if analysis.detailed_summary else [],
        "entities": json.loads(analysis.entities_json) if analysis.entities_json else [],
        "topics": json.loads(analysis.topics_json) if analysis.topics_json else [],
        "sentiment": analysis.sentiment or "",
        "action_items": json.loads(analysis.action_items_json) if analysis.action_items_json else [],
        "decisions": json.loads(analysis.decisions_json) if analysis.decisions_json else [],
    }
    if format == "json":
        return JSONResponse(content=data)
    return JSONResponse(content=data)
