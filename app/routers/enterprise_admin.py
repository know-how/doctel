"""
enterprise_admin.py — Admin CRUD for VISION 2.0 Enterprise Tables

Provides full CRUD (list, get, create, update, delete) for all enterprise
models introduced in migration 010. Follows the direct-SQLAlchemy pattern
from prompt_suggestions.py with prefix-based routing and require_role auth.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, Body, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete as sa_delete

from app.routers.deps import get_db, require_role, User, JSONResponse
from app.db.enterprise_models import (
    # Pillar 3
    DocAnalysisVersion,
    # Pillar 4
    QuotationSpan,
    # Pillar 6
    KnowledgeNode,
    KnowledgeEdge,
    # Pillar 9
    DocumentVersion,
    # Pillar 10
    Agent,
    AgentExecution,
    # Pillar 11
    HumanReview,
    # Pillar 12
    PromptTemplate,
    PromptTemplateVersion,
    # Pillar 13
    BenchmarkRun,
    BenchmarkResult,
    # Pillar 14
    CostRecord,
    BudgetAlert,
    # Pillar 15
    ConfidenceScore,
    # Pillar 17
    DepartmentRestriction,
    # Pillar 20
    InteractionAudit,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/enterprise", tags=["enterprise-admin"])


# =====================================================================
# Helper: Generic CRUD utilities
# =====================================================================

async def _get_entity_or_404(db: AsyncSession, model, entity_id: int):
    """Fetch an entity by id or return a 404 JSONResponse."""
    result = await db.execute(select(model).where(model.id == entity_id))
    entity = result.scalar_one_or_none()
    if not entity:
        return None
    return entity


def _not_found_response(entity_type: str = "Entity"):
    return JSONResponse(status_code=404, content={"error": f"{entity_type} not found"})


# ═════════════════════════════════════════════════════════════════════
# PILLAR 3 — DocAnalysisVersion CRUD
# ═════════════════════════════════════════════════════════════════════

@router.get("/doc-analysis-versions")
async def list_doc_analysis_versions(
    document_id: Optional[int] = Query(None),
    analysis_type: Optional[str] = Query(None),
    active_only: bool = Query(False),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """List document analysis versions with optional filtering."""
    query = select(DocAnalysisVersion)
    if document_id is not None:
        query = query.where(DocAnalysisVersion.document_id == document_id)
    if analysis_type:
        query = query.where(DocAnalysisVersion.analysis_type == analysis_type)
    if active_only:
        query = query.where(DocAnalysisVersion.is_active == True)
    query = query.order_by(DocAnalysisVersion.document_id, DocAnalysisVersion.version.desc()).limit(limit)
    result = await db.execute(query)
    items = result.scalars().all()
    return {"items": [i.to_dict() for i in items], "count": len(items)}


@router.get("/doc-analysis-versions/{version_id}")
async def get_doc_analysis_version(
    version_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """Get a single document analysis version."""
    item = await _get_entity_or_404(db, DocAnalysisVersion, version_id)
    if item is None:
        return _not_found_response("DocAnalysisVersion")
    return {"item": item.to_dict()}


@router.delete("/doc-analysis-versions/{version_id}")
async def delete_doc_analysis_version(
    version_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """Delete a document analysis version."""
    item = await _get_entity_or_404(db, DocAnalysisVersion, version_id)
    if item is None:
        return _not_found_response("DocAnalysisVersion")
    await db.delete(item)
    await db.commit()
    logger.info(f"Deleted DocAnalysisVersion {version_id} by user {user.id}")
    return {"message": "DocAnalysisVersion deleted"}


# ═════════════════════════════════════════════════════════════════════
# PILLAR 4 — QuotationSpan CRUD
# ═════════════════════════════════════════════════════════════════════

@router.get("/quotation-spans")
async def list_quotation_spans(
    message_id: Optional[int] = Query(None),
    document_id: Optional[int] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """List quotation spans with optional filtering."""
    query = select(QuotationSpan)
    if message_id is not None:
        query = query.where(QuotationSpan.message_id == message_id)
    if document_id is not None:
        query = query.where(QuotationSpan.document_id == document_id)
    query = query.order_by(QuotationSpan.created_at.desc()).limit(limit)
    result = await db.execute(query)
    items = result.scalars().all()
    return {"items": [i.to_dict() for i in items], "count": len(items)}


@router.get("/quotation-spans/{span_id}")
async def get_quotation_span(
    span_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """Get a single quotation span."""
    item = await _get_entity_or_404(db, QuotationSpan, span_id)
    if item is None:
        return _not_found_response("QuotationSpan")
    return {"item": item.to_dict()}


# ═════════════════════════════════════════════════════════════════════
# PILLAR 6 — Knowledge Graph CRUD
# ═════════════════════════════════════════════════════════════════════

@router.get("/knowledge-nodes")
async def list_knowledge_nodes(
    node_type: Optional[str] = Query(None),
    label: Optional[str] = Query(None),
    active_only: bool = Query(True),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """List knowledge graph nodes with optional filtering."""
    query = select(KnowledgeNode)
    if node_type:
        query = query.where(KnowledgeNode.node_type == node_type)
    if label:
        query = query.where(KnowledgeNode.label.ilike(f"%{label}%"))
    if active_only:
        query = query.where(KnowledgeNode.is_active == True)
    query = query.order_by(KnowledgeNode.importance.desc()).limit(limit)
    result = await db.execute(query)
    items = result.scalars().all()
    return {"items": [i.to_dict() for i in items], "count": len(items)}


@router.get("/knowledge-nodes/{node_id}")
async def get_knowledge_node(
    node_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """Get a single knowledge node."""
    item = await _get_entity_or_404(db, KnowledgeNode, node_id)
    if item is None:
        return _not_found_response("KnowledgeNode")
    return {"item": item.to_dict()}


@router.get("/knowledge-edges")
async def list_knowledge_edges(
    source_node_id: Optional[int] = Query(None),
    target_node_id: Optional[int] = Query(None),
    relation: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """List knowledge graph edges with optional filtering."""
    query = select(KnowledgeEdge)
    if source_node_id is not None:
        query = query.where(KnowledgeEdge.source_node_id == source_node_id)
    if target_node_id is not None:
        query = query.where(KnowledgeEdge.target_node_id == target_node_id)
    if relation:
        query = query.where(KnowledgeEdge.relation == relation)
    query = query.limit(limit)
    result = await db.execute(query)
    items = result.scalars().all()
    return {"items": [i.to_dict() for i in items], "count": len(items)}


# ═════════════════════════════════════════════════════════════════════
# PILLAR 9 — DocumentVersion CRUD
# ═════════════════════════════════════════════════════════════════════

@router.get("/document-versions")
async def list_document_versions(
    document_id: Optional[int] = Query(None),
    superseded_only: bool = Query(False),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """List document versions with optional filtering."""
    query = select(DocumentVersion)
    if document_id is not None:
        query = query.where(DocumentVersion.document_id == document_id)
    if superseded_only:
        query = query.where(DocumentVersion.is_superseded == True)
    query = query.order_by(DocumentVersion.document_id, DocumentVersion.version_number).limit(limit)
    result = await db.execute(query)
    items = result.scalars().all()
    return {"items": [i.to_dict() for i in items], "count": len(items)}


@router.get("/document-versions/{version_id}")
async def get_document_version(
    version_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """Get a single document version."""
    item = await _get_entity_or_404(db, DocumentVersion, version_id)
    if item is None:
        return _not_found_response("DocumentVersion")
    return {"item": item.to_dict()}


@router.delete("/document-versions/{version_id}")
async def delete_document_version(
    version_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """Delete a document version."""
    item = await _get_entity_or_404(db, DocumentVersion, version_id)
    if item is None:
        return _not_found_response("DocumentVersion")
    await db.delete(item)
    await db.commit()
    logger.info(f"Deleted DocumentVersion {version_id} by user {user.id}")
    return {"message": "DocumentVersion deleted"}


# ═════════════════════════════════════════════════════════════════════
# PILLAR 10 — Agent CRUD
# ═════════════════════════════════════════════════════════════════════

@router.get("/agents")
async def list_agents(
    agent_type: Optional[str] = Query(None),
    active_only: bool = Query(True),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """List agents with optional filtering."""
    query = select(Agent)
    if agent_type:
        query = query.where(Agent.agent_type == agent_type)
    if active_only:
        query = query.where(Agent.is_active == True)
    query = query.order_by(Agent.name).limit(limit)
    result = await db.execute(query)
    items = result.scalars().all()
    return {"items": [i.to_dict() for i in items], "count": len(items)}


@router.get("/agents/{agent_id}")
async def get_agent(
    agent_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """Get a single agent by DB primary key."""
    item = await _get_entity_or_404(db, Agent, agent_id)
    if item is None:
        return _not_found_response("Agent")
    return {"item": item.to_dict()}


@router.post("/agents")
async def create_agent(
    name: str = Body(..., min_length=1, max_length=255),
    agent_type: str = Body(..., max_length=64),
    description: str = Body(""),
    system_prompt: str = Body(""),
    model_id: str = Body(""),
    provider_id: str = Body(""),
    temperature: float = Body(0.7),
    max_tokens: int = Body(4096),
    allow_delegation: bool = Body(False),
    allowed_tools: List[str] = Body([]),
    config: dict = Body({}),
    owner_role: str = Body("admin"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """Create a new agent."""
    import json
    import uuid
    agent = Agent(
        agent_id=f"ag_{uuid.uuid4().hex[:12]}",
        name=name,
        agent_type=agent_type,
        description=description,
        system_prompt=system_prompt,
        model_id=model_id,
        provider_id=provider_id,
        temperature=temperature,
        max_tokens=max_tokens,
        allow_delegation=allow_delegation,
        allowed_tools_json=json.dumps(allowed_tools),
        config_json=json.dumps(config),
        owner_role=owner_role,
        is_active=True,
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    logger.info(f"Created agent '{name}' (id={agent.id}) by user {user.id}")
    return {"item": agent.to_dict(), "message": "Agent created"}


@router.put("/agents/{agent_id}")
async def update_agent(
    agent_id: int,
    name: Optional[str] = Body(None, max_length=255),
    agent_type: Optional[str] = Body(None, max_length=64),
    description: Optional[str] = Body(None),
    system_prompt: Optional[str] = Body(None),
    model_id: Optional[str] = Body(None),
    provider_id: Optional[str] = Body(None),
    temperature: Optional[float] = Body(None),
    max_tokens: Optional[int] = Body(None),
    allow_delegation: Optional[bool] = Body(None),
    allowed_tools: Optional[List[str]] = Body(None),
    config: Optional[dict] = Body(None),
    is_active: Optional[bool] = Body(None),
    owner_role: Optional[str] = Body(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """Update an existing agent."""
    item = await _get_entity_or_404(db, Agent, agent_id)
    if item is None:
        return _not_found_response("Agent")

    import json
    if name is not None:
        item.name = name
    if agent_type is not None:
        item.agent_type = agent_type
    if description is not None:
        item.description = description
    if system_prompt is not None:
        item.system_prompt = system_prompt
    if model_id is not None:
        item.model_id = model_id
    if provider_id is not None:
        item.provider_id = provider_id
    if temperature is not None:
        item.temperature = temperature
    if max_tokens is not None:
        item.max_tokens = max_tokens
    if allow_delegation is not None:
        item.allow_delegation = allow_delegation
    if allowed_tools is not None:
        item.allowed_tools_json = json.dumps(allowed_tools)
    if config is not None:
        item.config_json = json.dumps(config)
    if is_active is not None:
        item.is_active = is_active
    if owner_role is not None:
        item.owner_role = owner_role

    await db.commit()
    await db.refresh(item)
    logger.info(f"Updated agent {agent_id} by user {user.id}")
    return {"item": item.to_dict(), "message": "Agent updated"}


@router.delete("/agents/{agent_id}")
async def delete_agent(
    agent_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """Delete an agent."""
    item = await _get_entity_or_404(db, Agent, agent_id)
    if item is None:
        return _not_found_response("Agent")
    await db.delete(item)
    await db.commit()
    logger.info(f"Deleted agent {agent_id} by user {user.id}")
    return {"message": "Agent deleted"}


# ═════════════════════════════════════════════════════════════════════
# PILLAR 10 — AgentExecution (read-only list/get)
# ═════════════════════════════════════════════════════════════════════

@router.get("/agent-executions")
async def list_agent_executions(
    agent_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    user_id: Optional[int] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """List agent executions with optional filtering."""
    query = select(AgentExecution)
    if agent_id is not None:
        query = query.where(AgentExecution.agent_id == agent_id)
    if status:
        query = query.where(AgentExecution.status == status)
    if user_id is not None:
        query = query.where(AgentExecution.user_id == user_id)
    query = query.order_by(AgentExecution.created_at.desc()).limit(limit)
    result = await db.execute(query)
    items = result.scalars().all()
    return {"items": [i.to_dict() for i in items], "count": len(items)}


@router.get("/agent-executions/{exec_id}")
async def get_agent_execution(
    exec_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """Get a single agent execution."""
    item = await _get_entity_or_404(db, AgentExecution, exec_id)
    if item is None:
        return _not_found_response("AgentExecution")
    return {"item": item.to_dict()}


# ═════════════════════════════════════════════════════════════════════
# PILLAR 11 — HumanReview CRUD
# ═════════════════════════════════════════════════════════════════════

@router.get("/human-reviews")
async def list_human_reviews(
    review_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    reviewer_id: Optional[int] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """List human reviews with optional filtering."""
    query = select(HumanReview)
    if review_type:
        query = query.where(HumanReview.review_type == review_type)
    if status:
        query = query.where(HumanReview.status == status)
    if reviewer_id is not None:
        query = query.where(HumanReview.reviewer_id == reviewer_id)
    query = query.order_by(HumanReview.created_at.desc()).limit(limit)
    result = await db.execute(query)
    items = result.scalars().all()
    return {"items": [i.to_dict() for i in items], "count": len(items)}


@router.get("/human-reviews/{review_id}")
async def get_human_review(
    review_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """Get a single human review."""
    item = await _get_entity_or_404(db, HumanReview, review_id)
    if item is None:
        return _not_found_response("HumanReview")
    return {"item": item.to_dict()}


@router.put("/human-reviews/{review_id}")
async def update_human_review(
    review_id: int,
    status: Optional[str] = Body(None),
    review_comment: Optional[str] = Body(None),
    content_after: Optional[str] = Body(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """Update a human review (approve/reject/request changes)."""
    item = await _get_entity_or_404(db, HumanReview, review_id)
    if item is None:
        return _not_found_response("HumanReview")

    if status is not None:
        item.status = status
    if review_comment is not None:
        item.review_comment = review_comment
    if content_after is not None:
        item.content_after = content_after
    if status in ("approved", "rejected"):
        item.reviewer_id = user.id

    await db.commit()
    await db.refresh(item)
    logger.info(f"Updated HumanReview {review_id} status={status} by user {user.id}")
    return {"item": item.to_dict(), "message": "HumanReview updated"}


# ═════════════════════════════════════════════════════════════════════
# PILLAR 12 — PromptTemplate CRUD
# ═════════════════════════════════════════════════════════════════════

@router.get("/prompt-templates")
async def list_prompt_templates(
    task_type: Optional[str] = Query(None),
    active_only: bool = Query(True),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """List prompt templates with optional filtering."""
    query = select(PromptTemplate)
    if task_type:
        query = query.where(PromptTemplate.task_type == task_type)
    if active_only:
        query = query.where(PromptTemplate.is_active == True)
    query = query.order_by(PromptTemplate.name).limit(limit)
    result = await db.execute(query)
    items = result.scalars().all()
    return {"items": [i.to_dict() for i in items], "count": len(items)}


@router.get("/prompt-templates/{template_id}")
async def get_prompt_template(
    template_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """Get a single prompt template by DB primary key."""
    item = await _get_entity_or_404(db, PromptTemplate, template_id)
    if item is None:
        return _not_found_response("PromptTemplate")
    return {"item": item.to_dict()}


@router.post("/prompt-templates")
async def create_prompt_template(
    name: str = Body(..., min_length=1, max_length=255),
    description: str = Body(""),
    task_type: str = Body("chat"),
    owner: str = Body(""),
    department: str = Body(""),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """Create a new prompt template."""
    import uuid
    template = PromptTemplate(
        template_id=f"pt_{uuid.uuid4().hex[:12]}",
        name=name,
        description=description,
        task_type=task_type,
        owner=owner,
        department=department,
        approval_status="draft",
        is_active=True,
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)
    logger.info(f"Created prompt template '{name}' (id={template.id}) by user {user.id}")

    # Create initial empty version
    version = PromptTemplateVersion(
        template_id=template.id,
        version=1,
        content="",
        change_notes="Initial version",
    )
    db.add(version)
    await db.commit()
    await db.refresh(template)

    return {"item": template.to_dict(), "message": "PromptTemplate created with v1"}


@router.put("/prompt-templates/{template_id}")
async def update_prompt_template(
    template_id: int,
    name: Optional[str] = Body(None, max_length=255),
    description: Optional[str] = Body(None),
    task_type: Optional[str] = Body(None, max_length=64),
    owner: Optional[str] = Body(None),
    department: Optional[str] = Body(None),
    approval_status: Optional[str] = Body(None),
    is_active: Optional[bool] = Body(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """Update a prompt template."""
    item = await _get_entity_or_404(db, PromptTemplate, template_id)
    if item is None:
        return _not_found_response("PromptTemplate")
    if name is not None:
        item.name = name
    if description is not None:
        item.description = description
    if task_type is not None:
        item.task_type = task_type
    if owner is not None:
        item.owner = owner
    if department is not None:
        item.department = department
    if approval_status is not None:
        item.approval_status = approval_status
    if is_active is not None:
        item.is_active = is_active
    await db.commit()
    await db.refresh(item)
    logger.info(f"Updated PromptTemplate {template_id} by user {user.id}")
    return {"item": item.to_dict(), "message": "PromptTemplate updated"}


@router.delete("/prompt-templates/{template_id}")
async def delete_prompt_template(
    template_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """Delete a prompt template (cascades to versions)."""
    item = await _get_entity_or_404(db, PromptTemplate, template_id)
    if item is None:
        return _not_found_response("PromptTemplate")
    await db.delete(item)
    await db.commit()
    logger.info(f"Deleted PromptTemplate {template_id} by user {user.id}")
    return {"message": "PromptTemplate deleted"}


# ─── PromptTemplateVersions (nested under templates) ───

@router.get("/prompt-templates/{template_id}/versions")
async def list_prompt_template_versions(
    template_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """List all versions for a specific prompt template."""
    # First verify the template exists
    tmpl = await _get_entity_or_404(db, PromptTemplate, template_id)
    if tmpl is None:
        return _not_found_response("PromptTemplate")

    result = await db.execute(
        select(PromptTemplateVersion)
        .where(PromptTemplateVersion.template_id == template_id)
        .order_by(PromptTemplateVersion.version.desc())
    )
    items = result.scalars().all()
    return {"items": [i.to_dict() for i in items], "count": len(items)}


@router.post("/prompt-templates/{template_id}/versions")
async def create_prompt_template_version(
    template_id: int,
    content: str = Body(..., min_length=1),
    change_notes: str = Body(""),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """Create a new version of a prompt template."""
    tmpl = await _get_entity_or_404(db, PromptTemplate, template_id)
    if tmpl is None:
        return _not_found_response("PromptTemplate")

    next_version = (tmpl.current_version or 0) + 1
    version = PromptTemplateVersion(
        template_id=template_id,
        version=next_version,
        content=content,
        change_notes=change_notes,
    )
    tmpl.current_version = next_version
    db.add(version)
    await db.commit()
    await db.refresh(version)
    logger.info(f"Created v{next_version} for PromptTemplate {template_id} by user {user.id}")
    return {"item": version.to_dict(), "message": f"Version {next_version} created"}


# ═════════════════════════════════════════════════════════════════════
# PILLAR 13 — BenchmarkRun CRUD
# ═════════════════════════════════════════════════════════════════════

@router.get("/benchmark-runs")
async def list_benchmark_runs(
    model_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """List benchmark runs with optional filtering."""
    query = select(BenchmarkRun)
    if model_id:
        query = query.where(BenchmarkRun.model_id == model_id)
    if status:
        query = query.where(BenchmarkRun.status == status)
    query = query.order_by(BenchmarkRun.created_at.desc()).limit(limit)
    result = await db.execute(query)
    items = result.scalars().all()
    return {"items": [i.to_dict() for i in items], "count": len(items)}


@router.get("/benchmark-runs/{run_id}")
async def get_benchmark_run(
    run_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """Get a single benchmark run (includes results)."""
    item = await _get_entity_or_404(db, BenchmarkRun, run_id)
    if item is None:
        return _not_found_response("BenchmarkRun")
    return {"item": item.to_dict(), "results": [r.to_dict() for r in item.results]}


@router.delete("/benchmark-runs/{run_id}")
async def delete_benchmark_run(
    run_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """Delete a benchmark run (cascades to results)."""
    item = await _get_entity_or_404(db, BenchmarkRun, run_id)
    if item is None:
        return _not_found_response("BenchmarkRun")
    await db.delete(item)
    await db.commit()
    logger.info(f"Deleted BenchmarkRun {run_id} by user {user.id}")
    return {"message": "BenchmarkRun deleted"}


# ═════════════════════════════════════════════════════════════════════
# PILLAR 14 — CostRecord CRUD
# ═════════════════════════════════════════════════════════════════════

@router.get("/cost-records")
async def list_cost_records(
    provider_id: Optional[str] = Query(None),
    model_id: Optional[str] = Query(None),
    user_id: Optional[int] = Query(None),
    department: Optional[str] = Query(None),
    source_type: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """List cost records with optional filtering."""
    query = select(CostRecord)
    if provider_id:
        query = query.where(CostRecord.provider_id == provider_id)
    if model_id:
        query = query.where(CostRecord.model_id == model_id)
    if user_id is not None:
        query = query.where(CostRecord.user_id == user_id)
    if department:
        query = query.where(CostRecord.department == department)
    if source_type:
        query = query.where(CostRecord.source_type == source_type)
    query = query.order_by(CostRecord.created_at.desc()).limit(limit)
    result = await db.execute(query)
    items = result.scalars().all()
    return {"items": [i.to_dict() for i in items], "count": len(items)}


@router.get("/cost-records/summary")
async def get_cost_summary(
    group_by: str = Query("department", pattern="^(department|provider|model|user|project)$"),
    period: Optional[str] = Query(None, pattern="^(daily|weekly|monthly|quarterly|yearly)$"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """Get aggregated cost summary grouped by a dimension."""
    # Map group_by to the actual column
    col_map = {
        "department": CostRecord.department,
        "provider": CostRecord.provider_id,
        "model": CostRecord.model_id,
        "user": CostRecord.user_id,
        "project": CostRecord.project_id,
    }
    group_col = col_map.get(group_by, CostRecord.department)

    query = select(
        group_col.label("dimension"),
        func.sum(CostRecord.total_cost).label("total_cost"),
        func.sum(CostRecord.tokens_total).label("total_tokens"),
        func.count(CostRecord.id).label("request_count"),
    )
    query = query.group_by(group_col).order_by(func.sum(CostRecord.total_cost).desc())

    result = await db.execute(query)
    rows = result.all()
    return {
        "items": [
            {
                "dimension": str(getattr(r, "dimension", r[0])),
                "totalCost": float(r.total_cost),
                "totalTokens": int(r.total_tokens),
                "requestCount": int(r.request_count),
            }
            for r in rows
        ],
        "count": len(rows),
    }


@router.get("/cost-records/{record_id}")
async def get_cost_record(
    record_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """Get a single cost record."""
    item = await _get_entity_or_404(db, CostRecord, record_id)
    if item is None:
        return _not_found_response("CostRecord")
    return {"item": item.to_dict()}


# ═════════════════════════════════════════════════════════════════════
# PILLAR 14 — BudgetAlert CRUD
# ═════════════════════════════════════════════════════════════════════

@router.get("/budget-alerts")
async def list_budget_alerts(
    scope_type: Optional[str] = Query(None),
    active_only: bool = Query(True),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """List budget alerts with optional filtering."""
    query = select(BudgetAlert)
    if scope_type:
        query = query.where(BudgetAlert.scope_type == scope_type)
    if active_only:
        query = query.where(BudgetAlert.is_active == True)
    query = query.order_by(BudgetAlert.scope_type, BudgetAlert.scope_id).limit(limit)
    result = await db.execute(query)
    items = result.scalars().all()
    return {"items": [i.to_dict() for i in items], "count": len(items)}


@router.post("/budget-alerts")
async def create_budget_alert(
    scope_type: str = Body(...),
    scope_id: str = Body(""),
    budget_amount: float = Body(...),
    currency: str = Body("USD"),
    period: str = Body("monthly"),
    alert_threshold_pct: float = Body(80.0),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """Create a new budget alert."""
    alert = BudgetAlert(
        scope_type=scope_type,
        scope_id=scope_id,
        budget_amount=budget_amount,
        currency=currency,
        period=period,
        alert_threshold_pct=alert_threshold_pct,
        is_active=True,
    )
    db.add(alert)
    await db.commit()
    await db.refresh(alert)
    logger.info(f"Created BudgetAlert for {scope_type}:{scope_id} by user {user.id}")
    return {"item": alert.to_dict(), "message": "BudgetAlert created"}


@router.put("/budget-alerts/{alert_id}")
async def update_budget_alert(
    alert_id: int,
    budget_amount: Optional[float] = Body(None),
    alert_threshold_pct: Optional[float] = Body(None),
    is_active: Optional[bool] = Body(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """Update a budget alert."""
    item = await _get_entity_or_404(db, BudgetAlert, alert_id)
    if item is None:
        return _not_found_response("BudgetAlert")
    if budget_amount is not None:
        item.budget_amount = budget_amount
    if alert_threshold_pct is not None:
        item.alert_threshold_pct = alert_threshold_pct
    if is_active is not None:
        item.is_active = is_active
    await db.commit()
    await db.refresh(item)
    return {"item": item.to_dict(), "message": "BudgetAlert updated"}


@router.delete("/budget-alerts/{alert_id}")
async def delete_budget_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """Delete a budget alert."""
    item = await _get_entity_or_404(db, BudgetAlert, alert_id)
    if item is None:
        return _not_found_response("BudgetAlert")
    await db.delete(item)
    await db.commit()
    return {"message": "BudgetAlert deleted"}


# ═════════════════════════════════════════════════════════════════════
# PILLAR 15 — ConfidenceScore CRUD
# ═════════════════════════════════════════════════════════════════════

@router.get("/confidence-scores")
async def list_confidence_scores(
    source_type: Optional[str] = Query(None),
    min_score: Optional[float] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """List confidence scores with optional filtering."""
    query = select(ConfidenceScore)
    if source_type:
        query = query.where(ConfidenceScore.source_type == source_type)
    if min_score is not None:
        query = query.where(ConfidenceScore.overall_score >= min_score)
    query = query.order_by(ConfidenceScore.created_at.desc()).limit(limit)
    result = await db.execute(query)
    items = result.scalars().all()
    return {"items": [i.to_dict() for i in items], "count": len(items)}


# ═════════════════════════════════════════════════════════════════════
# PILLAR 17 — DepartmentRestriction CRUD
# ═════════════════════════════════════════════════════════════════════

@router.get("/department-restrictions")
async def list_department_restrictions(
    department: Optional[str] = Query(None),
    restriction_type: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """List department restrictions with optional filtering."""
    query = select(DepartmentRestriction)
    if department:
        query = query.where(DepartmentRestriction.department == department)
    if restriction_type:
        query = query.where(DepartmentRestriction.restriction_type == restriction_type)
    query = query.order_by(DepartmentRestriction.department, DepartmentRestriction.restriction_type).limit(limit)
    result = await db.execute(query)
    items = result.scalars().all()
    return {"items": [i.to_dict() for i in items], "count": len(items)}


@router.post("/department-restrictions")
async def create_department_restriction(
    department: str = Body(...),
    restriction_type: str = Body(...),
    restriction_id: str = Body(...),
    is_allowed: bool = Body(True),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """Create a department restriction."""
    restriction = DepartmentRestriction(
        department=department,
        restriction_type=restriction_type,
        restriction_id=restriction_id,
        is_allowed=is_allowed,
    )
    db.add(restriction)
    await db.commit()
    await db.refresh(restriction)
    logger.info(f"Created DepartmentRestriction for {department}/{restriction_type}/{restriction_id}")
    return {"item": restriction.to_dict(), "message": "DepartmentRestriction created"}


@router.delete("/department-restrictions/{restriction_id}")
async def delete_department_restriction(
    restriction_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """Delete a department restriction."""
    item = await _get_entity_or_404(db, DepartmentRestriction, restriction_id)
    if item is None:
        return _not_found_response("DepartmentRestriction")
    await db.delete(item)
    await db.commit()
    return {"message": "DepartmentRestriction deleted"}


# ═════════════════════════════════════════════════════════════════════
# PILLAR 20 — InteractionAudit (read-only list/get)
# ═════════════════════════════════════════════════════════════════════

@router.get("/interaction-audits")
async def list_interaction_audits(
    user_id: Optional[int] = Query(None),
    provider_id: Optional[str] = Query(None),
    model_id: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    session_id: Optional[int] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """List interaction audits with optional filtering."""
    query = select(InteractionAudit)
    if user_id is not None:
        query = query.where(InteractionAudit.user_id == user_id)
    if provider_id:
        query = query.where(InteractionAudit.provider_id == provider_id)
    if model_id:
        query = query.where(InteractionAudit.model_id == model_id)
    if department:
        query = query.where(InteractionAudit.department == department)
    if session_id is not None:
        query = query.where(InteractionAudit.session_id == session_id)
    query = query.order_by(InteractionAudit.created_at.desc()).limit(limit)
    result = await db.execute(query)
    items = result.scalars().all()
    return {"items": [i.to_dict() for i in items], "count": len(items)}


@router.get("/interaction-audits/{audit_id}")
async def get_interaction_audit(
    audit_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(["admin"])),
):
    """Get a single interaction audit record."""
    item = await _get_entity_or_404(db, InteractionAudit, audit_id)
    if item is None:
        return _not_found_response("InteractionAudit")
    return {"item": item.to_dict()}
