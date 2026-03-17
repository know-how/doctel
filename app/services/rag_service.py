import json
import logging
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.db.models import Message, Session, Chunk, Document
from app.utils.ollama_client import ollama
from app.utils.chroma_client import chroma
from app.services.model_router import select_text_model

logger = logging.getLogger(__name__)

def _dedupe_keep_order(items: list[dict]) -> list[dict]:
    seen: set[tuple] = set()
    out: list[dict] = []
    for it in items:
        key = (it.get("filename"), it.get("chunk_index"), it.get("project_id"), it.get("document_id"))
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out

async def get_rag_answer_scoped(
    project_ids: List[int],
    user_query: str,
    db: AsyncSession,
    document_id: Optional[int] = None,
    model_name: Optional[str] = None,
    force_policy: bool = False,
    force_diagram: bool = False,
):
    query_embedding = await ollama.embed(settings.embed_model, user_query)

    results_rows: list[dict] = []
    for pid in [int(p) for p in project_ids if p is not None]:
        try:
            where = {"document_id": document_id} if document_id is not None else None
            res = chroma.query(str(pid), query_embedding, top_k=settings.top_k, where=where)
        except Exception:
            continue
        docs = (res.get("documents") or [[]])[0] if isinstance(res, dict) else []
        metas = (res.get("metadatas") or [[]])[0] if isinstance(res, dict) else []
        dists = (res.get("distances") or [[]])[0] if isinstance(res, dict) else []
        for i, txt in enumerate(docs or []):
            meta = metas[i] if i < len(metas) else {}
            dist = dists[i] if i < len(dists) else None
            results_rows.append(
                {
                    "project_id": pid,
                    "document_id": meta.get("document_id"),
                    "filename": meta.get("filename", "Unknown"),
                    "chunk_index": meta.get("chunk_index", 0),
                    "text": txt or "",
                    "distance": float(dist) if dist is not None else 1.0,
                }
            )

    results_rows.sort(key=lambda r: r.get("distance", 1.0))
    results_rows = results_rows[: max(6, int(settings.top_k or 6))]

    citations: list[dict] = []
    context_chunks: list[str] = []
    for r in results_rows:
        citations.append(
            {
                "filename": r["filename"],
                "chunk_index": int(r["chunk_index"] or 0),
                "text": (r["text"][:200] + "...") if r["text"] else "",
                "project_id": int(r["project_id"]),
                "document_id": int(r["document_id"]) if r.get("document_id") is not None else None,
            }
        )
        context_chunks.append(
            f"Source: {r['filename']}, Chunk {r['chunk_index']}\nContent: {r['text']}"
        )

    citations = _dedupe_keep_order(citations)
    context = "\n\n".join(context_chunks)
    used_files = list(dict.fromkeys([c.get("filename") for c in citations if c.get("filename")]))
    cross_refs = [{"filename": f, "reason": "Used as retrieval context"} for f in used_files[1:]]

    system_prompt = (
        "You are DocTel (ZETDC), a local, privacy-first analyst. "
        "Use ONLY the provided context to answer. "
        "Always include short citations like [Doc: <filename>, chunk <n>]. "
        "Use ZETDC terminology (transmission, distribution, substations, feeders, SCADA, HSE, ZERA compliance). "
    )
    if force_policy:
        system_prompt += (
            "When asked for a policy, output a draft policy with sections: "
            "Purpose, Scope, Definitions, Responsibilities, Procedures, Exceptions, Version Control, References. "
            "Cite internal sources."
        )
    if force_diagram:
        system_prompt += (
            "When asked for a process/diagram, output: "
            "1) concise numbered steps, 2) a Mermaid flowchart fenced block, 3) a one-sentence drawing prompt."
        )

    user_prompt = f"Question: {user_query}\n\nContext:\n{context}"
    chosen = model_name or select_text_model("rag")
    answer_text = await ollama.generate(chosen, user_prompt, system=system_prompt)

    mermaid_code = ""
    drawing_prompt = ""
    if "```mermaid" in answer_text:
        try:
            start = answer_text.find("```mermaid") + len("```mermaid")
            end = answer_text.find("```", start)
            mermaid_code = answer_text[start:end].strip()
        except Exception:
            pass
    if "Drawing Prompt:" in answer_text:
        try:
            drawing_prompt = answer_text.split("Drawing Prompt:")[1].split("\n")[0].strip()
        except Exception:
            pass

    return {
        "answer_text": answer_text,
        "mermaid_code": mermaid_code,
        "drawing_prompt": drawing_prompt,
        "citations": citations,
        "cross_references": cross_refs,
        "used_model": chosen,
    }

async def get_rag_answer(
    project_id: int,
    user_query: str,
    db: AsyncSession,
    session_id: Optional[int] = None,
    document_id: Optional[int] = None,
    model_name: Optional[str] = None,
):
    out = await get_rag_answer_scoped(
        [project_id],
        user_query,
        db,
        document_id=document_id,
        model_name=model_name,
        force_diagram=True,
    )
    if session_id:
        user_msg = Message(session_id=session_id, role="user", content=user_query)
        db.add(user_msg)
        assistant_msg = Message(
            session_id=session_id,
            role="assistant",
            content=out.get("answer_text", ""),
            citations_json=json.dumps(out.get("citations", [])),
        )
        db.add(assistant_msg)
        await db.commit()
    return out
