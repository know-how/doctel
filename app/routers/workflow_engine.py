"""
workflow_engine.py — DocTel Autonomous Workflow API

Endpoints for:
- Listing available workflow templates
- Executing workflows by objective
- Checking workflow execution status
- Getting workflow deliverables
- Forcing specific workflow types
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.routers.deps import get_db, require_role

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/workflows", tags=["Workflow Engine"])


# ═══════════════════════════════════════════════════════════════════════════════
# WORKFLOW TEMPLATES
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/templates", summary="List available workflow templates")
async def list_workflows(
    db=Depends(get_db),
    user=Depends(require_role(["admin", "analyst", "user"])),
):
    """List all available workflow definitions with descriptions and agents."""
    from app.services.workflow_engine_service import WorkflowEngine

    engine = WorkflowEngine(db)
    return engine.get_available_workflows()


@router.get("/templates/{workflow_type}", summary="Get workflow template details")
async def get_workflow_template(
    workflow_type: str,
    db=Depends(get_db),
    user=Depends(require_role(["admin", "analyst", "user"])),
):
    """Get details for a specific workflow template."""
    from app.services.workflow_engine_service import WorkflowEngine, WorkflowType

    try:
        wf_type = WorkflowType(workflow_type)
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown workflow type: {workflow_type}. "
                   f"Available: {[t.value for t in WorkflowType]}",
        )

    engine = WorkflowEngine(db)
    templates = engine.get_available_workflows()
    for t in templates:
        if t["workflow_type"] == workflow_type:
            return t
    raise HTTPException(status_code=404, detail="Template not found")


# ═══════════════════════════════════════════════════════════════════════════════
# WORKFLOW EXECUTION
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/execute", summary="Execute an autonomous workflow by objective")
async def run_workflow(
    body: dict[str, Any],
    db=Depends(get_db),
    user=Depends(require_role(["admin", "analyst"])),
):
    """Execute an autonomous workflow from an objective statement.

    Request body:
    {
        "objective": "Review the CRM Policy for compliance gaps",
        "session_id": 123,                     // optional
        "project_ids": [1, 2],                 // optional
        "document_id": "uuid",                 // optional
        "force_type": "policy_review"          // optional: override auto-detection
    }

    The engine automatically:
    1. Resolves the objective to a workflow type (policy_review, meeting_review, etc.)
    2. Selects appropriate agents (POLICY_AGENT, RISK_AGENT, etc.)
    3. Executes each agent step
    4. Generates deliverables (reports, registers, summaries)
    5. Stores results in agent memory
    """
    objective = (body.get("objective") or "").strip()
    if not objective:
        raise HTTPException(status_code=400, detail="objective is required")

    from app.services.workflow_engine_service import WorkflowEngine

    engine = WorkflowEngine(db)
    execution = await engine.resolve_and_execute(
        objective=objective,
        session_id=body.get("session_id"),
        project_ids=body.get("project_ids"),
        document_id=body.get("document_id"),
        force_type=body.get("force_type"),
    )

    return execution.to_dict()


@router.post("/execute/stream", summary="Execute workflow and return summary")
async def run_workflow_stream(
    body: dict[str, Any],
    db=Depends(get_db),
    user=Depends(require_role(["admin", "analyst"])),
):
    """Execute a workflow and return a simplified execution summary.

    Same as /execute but returns a flat summary suitable for prompt
    injection or API responses.
    """
    objective = (body.get("objective") or "").strip()
    if not objective:
        raise HTTPException(status_code=400, detail="objective is required")

    from app.services.workflow_engine_service import WorkflowEngine

    engine = WorkflowEngine(db)
    execution = await engine.resolve_and_execute(
        objective=objective,
        session_id=body.get("session_id"),
        project_ids=body.get("project_ids"),
        document_id=body.get("document_id"),
        force_type=body.get("force_type"),
    )

    return {
        "execution_id": execution.execution_id,
        "workflow_type": execution.workflow_type.value if hasattr(execution.workflow_type, 'value') else execution.workflow_type,
        "status": execution.status,
        "execution_summary": execution.execution_summary,
        "entities": execution.merged_entities,
        "deliverables": list(execution.deliverables.keys()),
        "error": execution.error,
        "total_duration_ms": execution.total_duration_ms,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# WORKFLOW STATUS & RESULTS
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/executions", summary="List workflow executions from database")
async def list_executions(
    limit: int = Query(20, description="Max executions to return"),
    status: Optional[str] = Query(None, description="Filter by status (pending|running|completed|failed)"),
    session_id: Optional[int] = Query(None, description="Filter by session ID"),
    db=Depends(get_db),
    user=Depends(require_role(["admin", "analyst"])),
):
    """List workflow executions from the database.

    Supports filtering by status, session_id, and limit.
    Persisted executions survive server restarts.
    """
    from app.services.workflow_engine_service import WorkflowEngine

    engine = WorkflowEngine(db)
    if session_id:
        return await engine.list_executions_by_session(session_id, limit=limit)
    return await engine.list_executions(limit=limit, status_filter=status)


@router.get("/executions/{execution_id}", summary="Get workflow execution status")
async def get_execution(
    execution_id: str,
    db=Depends(get_db),
    user=Depends(require_role(["admin", "analyst", "user"])),
):
    """Get the status and results of a workflow execution from the database."""
    from app.services.workflow_engine_service import WorkflowEngine

    engine = WorkflowEngine(db)
    execution = await engine.get_execution(execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    return execution


@router.get(
    "/executions/{execution_id}/deliverables",
    summary="Get workflow deliverables from database",
)
async def get_deliverables(
    execution_id: str,
    db=Depends(get_db),
    user=Depends(require_role(["admin", "analyst", "user"])),
):
    """Get the deliverables generated by a workflow execution."""
    from app.services.workflow_engine_service import WorkflowEngine

    engine = WorkflowEngine(db)
    execution = await engine.get_execution(execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    return execution.get("deliverables", {})


# ═══════════════════════════════════════════════════════════════════════════════
# INTENT RESOLUTION (for use by ask.py / copilot)
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/resolve", summary="Resolve an objective to a workflow type")
async def resolve_objective(
    body: dict[str, Any],
    db=Depends(get_db),
    user=Depends(require_role(["admin", "analyst", "user"])),
):
    """Resolve an objective to a workflow type without executing.

    Useful for showing the user what workflow will run before confirming.
    """
    objective = (body.get("objective") or "").strip()
    if not objective:
        raise HTTPException(status_code=400, detail="objective is required")

    from app.services.workflow_engine_service import WorkflowEngine, _infer_workflow_type, WorkflowType

    wf_type = _infer_workflow_type(objective)
    engine = WorkflowEngine(db)
    templates = engine.get_available_workflows()

    resolved = None
    for t in templates:
        if t["workflow_type"] == wf_type.value:
            resolved = t
            break

    return {
        "objective": objective,
        "resolved_type": wf_type.value,
        "template": resolved,
        "available_types": [t.value for t in WorkflowType],
    }
