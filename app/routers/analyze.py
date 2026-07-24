"""
DocTel analyze router.

Endpoints for document analysis: extraction, summaries, classification, and comparison.
"""

import asyncio

from fastapi import APIRouter

from app.routers.deps import (
    Body,
    Depends,
    User,
    AsyncSession,
    get_db,
    require_role,
    HTTPException,
    json,
    select,
    Document,
    DocAnalysis,
    _parse_document_id,
    select_model_with_fallback,
    logger,
)

router = APIRouter(tags=["analyze"])


# ─────────────────────────────────────────────────────────────────────────────
# Analyze API (extraction, summaries, classification, compare)
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/api/analyze/extraction")
async def api_analyze_extraction(
    payload: dict = Body(...),
    user: User = Depends(require_role(["admin", "analyst"])),
    db: AsyncSession = Depends(get_db),
):
    schema = (payload.get("schema") or "").strip()
    document_ids = payload.get("document_ids") or []
    if not schema:
        raise HTTPException(status_code=400, detail="schema is required")
    doc_int_ids = []
    for did in document_ids:
        try:
            doc_int_ids.append(_parse_document_id(str(did)))
        except Exception:
            pass
    if not doc_int_ids:
        raise HTTPException(status_code=400, detail="No valid document_ids")
    results = []
    for di in doc_int_ids:
        res = await db.execute(select(Document).where(Document.id == di))
        doc = res.scalar_one_or_none()
        if not doc:
            continue
        analysis_res = await db.execute(select(DocAnalysis).where(DocAnalysis.document_id == di))
        analysis = analysis_res.scalar_one_or_none()
        extracted = {}
        if analysis:
            extracted = {
                "entities": json.loads(analysis.entities_json) if analysis.entities_json else [],
                "topics": json.loads(analysis.topics_json) if analysis.topics_json else [],
                "action_items": json.loads(analysis.action_items_json) if analysis.action_items_json else [],
                "decisions": json.loads(analysis.decisions_json) if analysis.decisions_json else [],
            }
        results.append({"document_id": f"doc_{di}", "filename": doc.filename, "extracted": extracted})
    return {"results": results, "schema": schema}


@router.post("/api/analyze/summaries")
async def api_analyze_summaries(
    payload: dict = Body(...),
    user: User = Depends(require_role(["admin", "analyst"])),
    db: AsyncSession = Depends(get_db),
):
    document_ids = payload.get("document_ids") or []
    doc_int_ids = []
    for did in document_ids:
        try:
            doc_int_ids.append(_parse_document_id(str(did)))
        except Exception:
            pass
    if not doc_int_ids:
        raise HTTPException(status_code=400, detail="No valid document_ids")
    results = []
    for di in doc_int_ids:
        res = await db.execute(select(Document).where(Document.id == di))
        doc = res.scalar_one_or_none()
        if not doc:
            continue
        analysis_res = await db.execute(select(DocAnalysis).where(DocAnalysis.document_id == di))
        analysis = analysis_res.scalar_one_or_none()
        summary = ""
        if analysis:
            summary = analysis.executive_summary or ""
        results.append({"document_id": f"doc_{di}", "filename": doc.filename, "summary": summary})
    return {"summaries": results}


@router.post("/api/analyze/classification")
async def api_analyze_classification(
    payload: dict = Body(...),
    user: User = Depends(require_role(["admin", "analyst"])),
    db: AsyncSession = Depends(get_db),
):
    rules = (payload.get("rules") or "").strip()
    document_ids = payload.get("document_ids") or []
    model_name = (payload.get("model") or "").strip() or None
    doc_int_ids = []
    for did in document_ids:
        try:
            doc_int_ids.append(_parse_document_id(str(did)))
        except Exception:
            pass
    if not rules:
        raise HTTPException(status_code=400, detail="rules are required")
    if not doc_int_ids:
        raise HTTPException(status_code=400, detail="document_ids are required")

    from app.services.opencode_zen_service import is_configured as zen_cfg, generate as zen_gen
    from app.services.deepseek_service import is_configured as ds_cfg, generate as ds_gen
    from app.services.gemini_service import is_configured as gemini_cfg, generate as gemini_gen
    from app.services.huggingface_service import generate as hf_gen
    from app.utils.ollama_client import ollama

    results = []
    for di in doc_int_ids:
        res = await db.execute(select(Document).where(Document.id == di))
        doc = res.scalar_one_or_none()
        if not doc:
            continue
        analysis_res = await db.execute(select(DocAnalysis).where(DocAnalysis.document_id == di))
        analysis = analysis_res.scalar_one_or_none()

        summary = (analysis.executive_summary or "")[:2000] if analysis else ""
        try:
            topics = json.loads(analysis.topics_json) if analysis and analysis.topics_json else []
        except (json.JSONDecodeError, TypeError):
            topics = []
        doc_context = f"Filename: {doc.filename}\nSummary: {summary}\nCurrent tags: {topics}"

        classify_prompt = (
            f"Classify the following document according to these rules:\n{rules}\n\n"
            f"Document:\n{doc_context}\n\n"
            "Respond with ONLY valid JSON. Either a JSON array of tags "
            'e.g. ["Policy", "High Priority"] or an object with "tags" and "confidence" '
            'e.g. {"tags": ["Policy"], "confidence": 0.85}. '
            "Confidence must be a float between 0 and 1. No explanation, no markdown."
        )

        classification = "uncategorized"
        tags = []
        confidence = 0.0

        try:
            answer = None
            if model_name and model_name.startswith("zen/"):
                answer = await asyncio.wait_for(zen_gen(classify_prompt, model=model_name), timeout=30.0)
            elif model_name and model_name.startswith("huggingface/"):
                answer = await asyncio.wait_for(hf_gen(classify_prompt, model=model_name), timeout=30.0)
            elif model_name == "gemini-api":
                answer = await asyncio.wait_for(gemini_gen(classify_prompt), timeout=30.0)
            elif model_name == "deepseek-api":
                answer = await asyncio.wait_for(ds_gen(classify_prompt), timeout=30.0)
            elif model_name:
                answer = await ollama.generate(model_name, classify_prompt)

            if not answer and zen_cfg():
                answer = await asyncio.wait_for(zen_gen(classify_prompt), timeout=30.0)
            if not answer and ds_cfg():
                answer = await asyncio.wait_for(ds_gen(classify_prompt), timeout=30.0)
            if not answer and gemini_cfg():
                answer = await asyncio.wait_for(gemini_gen(classify_prompt), timeout=30.0)
            if not answer:
                doc_prompt = classify_prompt if not topics else classify_prompt + f"\nFallback: use existing tags {topics}"
                try:
                    fallback = await asyncio.wait_for(select_model_with_fallback(doc_prompt), timeout=45.0)
                    answer = fallback.get("answer", "") if isinstance(fallback, dict) else ""
                except Exception:
                    answer = ""

            if answer:
                cleaned = answer.strip().strip("```json").strip("```").strip()
                parsed = json.loads(cleaned)
                if isinstance(parsed, list):
                    tags = parsed
                    confidence = 0.5
                elif isinstance(parsed, dict):
                    tags = parsed.get("tags", parsed.get("classification", [parsed]))
                    confidence = float(parsed.get("confidence", 0.5))
                else:
                    tags = [str(parsed)]
                    confidence = 0.3
                classification = tags[0] if tags else "uncategorized"
                confidence = max(0.0, min(1.0, confidence))
        except Exception:
            logger.warning("Classification LLM failed for doc %s, using stored topics", di)
            confidence = 0.0

        if not tags and topics:
            classification = topics[0]
            tags = topics
            confidence = 0.2

        try:
            doc.tags_json = json.dumps(tags)
            db.add(doc)
            await db.commit()
        except Exception:
            pass

        results.append({
            "document_id": f"doc_{di}",
            "filename": doc.filename,
            "tags": tags,
            "classification": classification,
            "confidence": round(confidence, 2),
        })
    return {"classifications": results, "rules": rules}


@router.get("/api/analyze/enterprise-summary/{document_id}")
async def api_enterprise_summary(
    document_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve the enterprise summary for a document.

    Returns the structured enterprise summary JSON (doc_type, executive_summary,
    key_findings, responsibilities, risks, etc.) if available, or generates it
    on-demand if the document has been ingested but the enterprise summary
    was not yet generated.
    """
    doc_int = _parse_document_id(document_id)
    res = await db.execute(select(Document).where(Document.id == doc_int))
    doc = res.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Try to load existing enterprise summary
    analysis_res = await db.execute(select(DocAnalysis).where(DocAnalysis.document_id == doc_int))
    analysis = analysis_res.scalar_one_or_none()

    if analysis and analysis.summary_json:
        try:
            summary_data = json.loads(analysis.summary_json)
            return {
                "document_id": f"doc_{doc_int}",
                "filename": doc.filename,
                "summary": summary_data,
                "status": "available",
            }
        except (json.JSONDecodeError, TypeError):
            pass

    # If document is ingested but no enterprise summary, generate it on-demand
    if doc.ingestion_completed and not analysis:
        try:
            # Read the document text and generate summary
            from app.services.ingestion_service import extract_text
            extracted_text = await extract_text(doc.path, doc.mime_type)
            if extracted_text and len(extracted_text.strip()) > 50:
                from app.services.document_summarizer import generate_enterprise_summary
                summary_data = await generate_enterprise_summary(
                    db, extracted_text,
                    filename=doc.filename or "",
                    detected_type=doc.detected_type or "",
                )
                return {
                    "document_id": f"doc_{doc_int}",
                    "filename": doc.filename,
                    "summary": summary_data,
                    "status": "generated",
                }
        except Exception as e:
            logger.warning("[ENTERPRISE SUMMARY] On-demand generation failed for %s: %s", doc.filename, e)

    # Fallback: return what we have from legacy analysis
    data = {
        "document_id": f"doc_{doc_int}",
        "filename": doc.filename or "",
        "status": "legacy",
    }
    if analysis:
        data["summary"] = {
            "doc_type": analysis.doc_type or "generic",
            "executive_summary": analysis.executive_summary or "",
            "key_findings": [],
            "systems_entities": [],
            "responsibilities": [],
            "risks": [],
            "actions": [],
        }
    else:
        data["summary"] = None
    return data


@router.post("/api/analyze/compare")
async def api_analyze_compare(
    payload: dict = Body(...),
    user: User = Depends(require_role(["admin", "analyst"])),
    db: AsyncSession = Depends(get_db),
):
    doc_a_id = payload.get("doc_a") or ""
    doc_b_id = payload.get("doc_b") or ""
    if not doc_a_id or not doc_b_id:
        raise HTTPException(status_code=400, detail="doc_a and doc_b are required")
    try:
        a_int = _parse_document_id(str(doc_a_id))
        b_int = _parse_document_id(str(doc_b_id))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid document IDs")
    results = []
    for di, label in [(a_int, "doc_a"), (b_int, "doc_b")]:
        res = await db.execute(select(Document).where(Document.id == di))
        doc = res.scalar_one_or_none()
        if not doc:
            continue
        analysis_res = await db.execute(
            select(DocAnalysis).where(DocAnalysis.document_id == di).order_by(DocAnalysis.id.desc()).limit(1)
        )
        analysis = analysis_res.scalars().first()
        summary = analysis.executive_summary if analysis else ""
        sentiment = analysis.sentiment if analysis else ""
        try:
            topics = json.loads(analysis.topics_json) if analysis and analysis.topics_json else []
        except (json.JSONDecodeError, TypeError):
            topics = []
        results.append({
            "label": label,
            "document_id": f"doc_{di}",
            "filename": doc.filename,
            "summary": summary,
            "sentiment": sentiment,
            "topics": topics,
        })
    return {"comparison": results}
