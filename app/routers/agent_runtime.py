"""
agent_runtime.py — DocTel Agent Runtime API

Endpoints for:
- Memory management (CRUD, search, promote, forget)
- Agent execution (run single or multi-agent plans)
- Agent registry (list available agents)
- Session memory context
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.routers.deps import get_db, require_role
from app.services.agent_memory_service import AgentMemoryService, MemoryType
from app.services.agent_runtime_service import (
    AgentCoordinator,
    AgentRegistry,
    AgentType,
    execute_agent_plan,
)
from app.services.knowledge_orchestrator_service import detect_knowledge_intent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent", tags=["Agent Runtime"])


# ═══════════════════════════════════════════════════════════════════════════════
# MEMORY ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/memory", summary="Store a memory entry")
async def store_memory(
    agent_execution_id: int,
    key: str,
    value: Any,
    memory_type: str = Query("working", regex="^(working|episodic|semantic)$"),
    session_id: Optional[int] = None,
    ttl_seconds: Optional[int] = None,
    db=Depends(get_db),
    user=Depends(require_role(["admin", "analyst"])),
):
    """Store a memory entry in the agent memory store."""
    svc = AgentMemoryService(db)
    mem_id = await svc.store_memory(
        agent_execution_id=agent_execution_id,
        key=key,
        value=value,
        memory_type=memory_type,
        session_id=session_id,
        ttl_seconds=ttl_seconds,
    )
    if mem_id is None:
        raise HTTPException(status_code=500, detail="Failed to store memory")
    return {"status": "ok", "memory_id": mem_id}


@router.get("/memory/{memory_id}", summary="Get a memory entry")
async def get_memory(
    memory_id: int,
    db=Depends(get_db),
    user=Depends(require_role(["admin", "analyst"])),
):
    """Retrieve a single memory entry by ID."""
    svc = AgentMemoryService(db)
    entry = await svc.get_memory(memory_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Memory not found")
    return entry


@router.delete("/memory/{memory_id}", summary="Delete a memory entry")
async def delete_memory(
    memory_id: int,
    db=Depends(get_db),
    user=Depends(require_role(["admin", "analyst"])),
):
    """Delete a single memory entry."""
    svc = AgentMemoryService(db)
    success = await svc.delete_memory(memory_id)
    if not success:
        raise HTTPException(status_code=404, detail="Memory not found or could not be deleted")
    return {"status": "deleted", "memory_id": memory_id}


@router.patch("/memory/{memory_id}", summary="Update a memory entry")
async def update_memory(
    memory_id: int,
    value: Any,
    embedding: Optional[str] = None,
    db=Depends(get_db),
    user=Depends(require_role(["admin", "analyst"])),
):
    """Update the payload of an existing memory entry."""
    svc = AgentMemoryService(db)
    success = await svc.update_memory(
        memory_id=memory_id,
        value=value,
        embedding=embedding,
    )
    if not success:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"status": "updated", "memory_id": memory_id}


@router.get("/memory", summary="Search memories")
async def search_memory(
    key: Optional[str] = Query(None, description="Search by key"),
    memory_type: Optional[str] = Query(None, regex="^(working|episodic|semantic)$"),
    session_id: Optional[int] = Query(None, description="Filter by session ID"),
    agent_execution_id: Optional[int] = Query(None, description="Filter by execution ID"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db=Depends(get_db),
    user=Depends(require_role(["admin", "analyst", "user"])),
):
    """Search agent memories with optional filters."""
    svc = AgentMemoryService(db)
    return await svc.search_memory(
        key=key,
        memory_type=memory_type,
        session_id=session_id,
        agent_execution_id=agent_execution_id,
        limit=limit,
        offset=offset,
    )


@router.get("/memory/session/{session_id}", summary="Get session memories")
async def get_session_memories(
    session_id: int,
    memory_type: Optional[str] = Query(None, regex="^(working|episodic|semantic)$"),
    limit: int = Query(50, ge=1, le=200),
    db=Depends(get_db),
    user=Depends(require_role(["admin", "analyst", "user"])),
):
    """Get all memories for a session."""
    svc = AgentMemoryService(db)
    return await svc.get_session_memories(
        session_id=session_id,
        memory_type=memory_type,
        limit=limit,
    )


@router.post("/memory/promote/{memory_id}", summary="Promote a memory to a higher tier")
async def promote_memory(
    memory_id: int,
    target_type: str = Query(..., regex="^(episodic|semantic)$"),
    db=Depends(get_db),
    user=Depends(require_role(["admin", "analyst"])),
):
    """Promote a memory from working → episodic or episodic → semantic."""
    svc = AgentMemoryService(db)
    new_id = await svc.promote_memory(memory_id, target_type)
    if new_id is None:
        raise HTTPException(status_code=404, detail="Memory not found or could not be promoted")
    return {"status": "promoted", "new_memory_id": new_id, "target_type": target_type}


@router.post("/memory/promote-session/{session_id}", summary="Promote all session memories")
async def promote_session_memories(
    session_id: int,
    target_type: str = Query("episodic", regex="^(episodic|semantic)$"),
    db=Depends(get_db),
    user=Depends(require_role(["admin", "analyst"])),
):
    """Promote all working memories for a session to episodic or semantic."""
    svc = AgentMemoryService(db)
    count = await svc.promote_session_memories(session_id, target_type)
    return {"status": "promoted", "count": count, "target_type": target_type}


@router.delete("/memory/session/{session_id}", summary="Forget all session memories")
async def forget_session(
    session_id: int,
    db=Depends(get_db),
    user=Depends(require_role(["admin", "analyst"])),
):
    """Delete all memories for a session."""
    svc = AgentMemoryService(db)
    count = await svc.forget_session(session_id)
    return {"status": "forgotten", "count": count}


@router.post("/memory/clean-expired", summary="Clean expired memories")
async def clean_expired_memories(
    batch_size: int = Query(100, ge=1, le=500),
    db=Depends(get_db),
    user=Depends(require_role(["admin"])),
):
    """Remove all expired working memories."""
    svc = AgentMemoryService(db)
    count = await svc.clean_expired_memories(batch_size=batch_size)
    return {"status": "cleaned", "count": count}


@router.get("/memory/stats", summary="Memory statistics")
async def memory_stats(
    db=Depends(get_db),
    user=Depends(require_role(["admin"])),
):
    """Get aggregate memory statistics."""
    svc = AgentMemoryService(db)
    return await svc.get_memory_stats()


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT EXECUTION ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/agents", summary="List available agents")
async def list_agents(
    db=Depends(get_db),
    user=Depends(require_role(["admin", "analyst"])),
):
    """List all registered agents with their descriptions and capabilities."""
    import sqlalchemy as sa
    from app.db.enterprise_models import Agent

    try:
        result = await db.execute(sa.select(Agent).where(Agent.is_active == True))
        db_agents = result.scalars().all()
        if db_agents:
            return [a.to_dict() for a in db_agents]
    except Exception:
        pass

    # Fallback: return built-in defaults
    registry = AgentRegistry(db)
    return registry.get_all_agents()


@router.post("/execute", summary="Execute an agent plan for a query")
async def execute_agent(
    body: dict[str, Any],
    db=Depends(get_db),
    user=Depends(require_role(["admin", "analyst"])),
):
    """Execute an agent plan for a given query.

    Request body:
    {
        "query": "Summarize this meeting",
        "intent": "meeting_analysis",  // optional: auto-detected if omitted
        "session_id": 123,             // optional: for memory scoping
        "document_id": "uuid",         // optional: for scoped retrieval
        "project_ids": [1, 2],         // optional: for scoped retrieval
        "audio_transcript": "..."      // optional: for media analysis
    }
    """
    query = body.get("query", "")
    if not query:
        raise HTTPException(status_code=400, detail="query is required")

    intent = body.get("intent")
    if not intent:
        intent = detect_knowledge_intent(query).value

    coordinator = AgentCoordinator(db)
    await coordinator.initialize()

    bundle = await coordinator.execute_agent_plan(
        intent=intent,
        user_query=query,
        session_id=body.get("session_id"),
        document_id=body.get("document_id"),
        project_ids=body.get("project_ids"),
        audio_transcript=body.get("audio_transcript"),
    )

    return bundle.to_dict()


@router.post("/execute/stream", summary="Execute an agent plan with streaming context")
async def execute_agent_stream(
    body: dict[str, Any],
    db=Depends(get_db),
    user=Depends(require_role(["admin", "analyst"])),
):
    """Execute an agent plan and return the execution summary text.

    Same as /execute but returns a flat text summary instead of the
    full bundle, suitable for streaming or injection into prompts.
    """
    query = body.get("query", "")
    if not query:
        raise HTTPException(status_code=400, detail="query is required")

    intent = body.get("intent")
    if not intent:
        intent = detect_knowledge_intent(query).value

    coordinator = AgentCoordinator(db)
    await coordinator.initialize()

    bundle = await coordinator.execute_agent_plan(
        intent=intent,
        user_query=query,
        session_id=body.get("session_id"),
        document_id=body.get("document_id"),
        project_ids=body.get("project_ids"),
        audio_transcript=body.get("audio_transcript"),
    )

    return {
        "execution_summary": bundle.execution_summary,
        "entities": bundle.merged_entities,
        "actions": bundle.merged_actions,
        "decisions": bundle.merged_decisions,
        "risks": bundle.merged_risks,
        "agent_results": [ar.to_dict() for ar in bundle.agent_results],
        "total_duration_ms": bundle.total_duration_ms,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# MEMORY CONTEXT FOR PROMPT INJECTION
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/memory-context/{session_id}", summary="Build memory context for LLM prompt")
async def get_memory_context(
    session_id: int,
    max_tokens: int = Query(2000, ge=100, le=8000),
    db=Depends(get_db),
    user=Depends(require_role(["admin", "analyst", "user"])),
):
    """Build a memory context string for injection into LLM prompts."""
    coordinator = AgentCoordinator(db)
    await coordinator.initialize()
    context = await coordinator.get_session_memory_context(
        session_id=session_id,
        max_tokens=max_tokens,
    )
    return {"session_id": session_id, "context": context, "context_length": len(context)}


@router.post("/memory-context/build", summary="Build memory + audio context for prompts")
async def build_memory_context(
    body: dict[str, Any],
    db=Depends(get_db),
    user=Depends(require_role(["admin", "analyst", "user"])),
):
    """Build a complete memory + audio context section for prompt injection.

    Request body:
    {
        "session_id": 123,
        "audio_transcript": "..."  // optional
    }
    """
    coordinator = AgentCoordinator(db)
    await coordinator.initialize()
    context = await coordinator.build_memory_prompt_section(
        session_id=body.get("session_id"),
        audio_transcript=body.get("audio_transcript"),
    )
    return {
        "context": context,
        "context_length": len(context),
    }
