"""
enterprise_models.py — DocTel Vision 2.0 Enterprise Schema Expansion

Adds database tables for all 20 pillars that were missing or incomplete:

  Pillar  3 — DocAnalysisVersion (regeneratable intelligence)
  Pillar  4 — QuotationSpan (verified quotations)
  Pillar  6 — KnowledgeNode, KnowledgeEdge (knowledge graph)
  Pillar  9 — DocumentVersion (document version intelligence)
  Pillar 10 — Agent, AgentExecution, AgentTool (agent framework)
  Pillar 11 — HumanReview, ReviewAssignment (human review workflows)
  Pillar 12 — PromptTemplate, PromptTemplateVersion (prompt governance)
  Pillar 13 — BenchmarkRun, BenchmarkResult (model evaluation)
  Pillar 14 — CostRecord, BudgetAlert (cost governance)
  Pillar 15 — ConfidenceScore (trust & confidence scoring)
  Pillar 17 — DepartmentRestriction, ProviderRestriction (security & governance)
  Pillar 20 — InteractionAudit (full auditability)

Every table references existing app.db.models or app.db.config_models FKs.
"""

from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Text, Float, Boolean, DateTime,
    ForeignKey, JSON, UniqueConstraint, Index,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


# ═══════════════════════════════════════════════════════════════════════════════
# PILLAR 3 — REGENERATABLE DOCUMENT INTELLIGENCE
# ═══════════════════════════════════════════════════════════════════════════════

class DocAnalysisVersion(Base):
    """Versioned document analysis — enables regeneration without re-ingestion.

    Each row captures one generation of analysis for a document.
    Users can compare versions and revert.
    """
    __tablename__ = "doc_analysis_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"),
                         nullable=False, index=True)
    version = Column(Integer, nullable=False, default=1)
    analysis_type = Column(String(32), nullable=False)  # summary | extraction | classification

    # Summary fields
    executive_summary = Column(Text, default="")
    detailed_summary = Column(Text, default="")

    # Extraction fields
    entities_json = Column(Text, default="[]")
    topics_json = Column(Text, default="[]")
    actions_json = Column(Text, default="[]")
    decisions_json = Column(Text, default="[]")

    # Classification fields
    categories_json = Column(Text, default="[]")
    sentiment = Column(String(64), default="")
    risk_score = Column(Float, nullable=True)

    # Provenance
    model_id = Column(String(255), default="")
    provider_id = Column(String(128), default="")
    prompt_version = Column(Integer, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    token_count = Column(Integer, nullable=True)

    # Status
    is_active = Column(Boolean, default=True)  # Currently active/displayed version
    status = Column(String(32), default="completed")  # pending | running | completed | failed
    error_message = Column(Text, default="")

    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("document_id", "analysis_type", "version",
                         name="uq_doc_analysis_version"),
        Index("idx_doc_analysis_active", "document_id", "analysis_type", "is_active"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "documentId": self.document_id,
            "version": self.version,
            "analysisType": self.analysis_type,
            "executiveSummary": self.executive_summary,
            "detailedSummary": self.detailed_summary,
            "entities": json.loads(self.entities_json) if self.entities_json else [],
            "topics": json.loads(self.topics_json) if self.topics_json else [],
            "actions": json.loads(self.actions_json) if self.actions_json else [],
            "decisions": json.loads(self.decisions_json) if self.decisions_json else [],
            "categories": json.loads(self.categories_json) if self.categories_json else [],
            "sentiment": self.sentiment,
            "riskScore": self.risk_score,
            "modelId": self.model_id,
            "providerId": self.provider_id,
            "promptVersion": self.prompt_version,
            "durationMs": self.duration_ms,
            "tokenCount": self.token_count,
            "isActive": self.is_active,
            "status": self.status,
            "errorMessage": self.error_message,
            "createdBy": self.created_by,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# PILLAR 4 — VERIFIED CITATIONS & QUOTATIONS
# ═══════════════════════════════════════════════════════════════════════════════

class QuotationSpan(Base):
    """A verified quotation extracted from a source document.

    Every quotation shown to users must be linked to an actual source chunk
    with character-level precision. LLMs are prohibited from inventing quotes.
    """
    __tablename__ = "quotation_spans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(Integer, ForeignKey("messages.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="SET NULL"),
                         nullable=True)
    chunk_id = Column(Integer, ForeignKey("chunks.id", ondelete="SET NULL"),
                      nullable=True)
    filename = Column(String(512), default="")
    quote_text = Column(Text, nullable=False)
    source_location = Column(String(255), default="")  # e.g. "Page 3, Paragraph 2"
    character_offset = Column(Integer, nullable=True)
    citation_ref = Column(String(255), default="")
    confidence = Column(Float, default=1.0)
    verified = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_quotation_message", "message_id"),
        Index("idx_quotation_document", "document_id"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "messageId": self.message_id,
            "documentId": self.document_id,
            "chunkId": self.chunk_id,
            "filename": self.filename,
            "quoteText": self.quote_text,
            "sourceLocation": self.source_location,
            "characterOffset": self.character_offset,
            "citationRef": self.citation_ref,
            "confidence": self.confidence,
            "verified": self.verified,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# PILLAR 6 — ENTERPRISE KNOWLEDGE GRAPH
# ═══════════════════════════════════════════════════════════════════════════════

class KnowledgeNode(Base):
    """A node in the enterprise knowledge graph.

    Nodes represent entities, topics, decisions, people, projects, documents, etc.
    """
    __tablename__ = "knowledge_nodes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    node_id = Column(String(128), unique=True, nullable=False, index=True)
    node_type = Column(String(64), nullable=False, index=True)
    # person | topic | entity | decision | project | document | action | policy | meeting
    label = Column(String(255), nullable=False)
    description = Column(Text, default="")
    metadata_json = Column(Text, default="{}")
    source_document_id = Column(Integer, ForeignKey("documents.id", ondelete="SET NULL"),
                                nullable=True)
    source_project_id = Column(Integer, ForeignKey("projects.id", ondelete="SET NULL"),
                               nullable=True)
    importance = Column(Float, default=0.0)  # 0.0 - 1.0 centrality score
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_node_type_importance", "node_type", "importance"),
    )

    edges_from = relationship("KnowledgeEdge", foreign_keys="KnowledgeEdge.source_node_id",
                              back_populates="source_node", lazy="selectin")
    edges_to = relationship("KnowledgeEdge", foreign_keys="KnowledgeEdge.target_node_id",
                            back_populates="target_node", lazy="selectin")

    def to_dict(self) -> dict:
        return {
            "id": self.node_id,
            "nodeType": self.node_type,
            "label": self.label,
            "description": self.description,
            "metadata": json.loads(self.metadata_json) if self.metadata_json else {},
            "sourceDocumentId": self.source_document_id,
            "sourceProjectId": self.source_project_id,
            "importance": self.importance,
            "isActive": self.is_active,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }


class KnowledgeEdge(Base):
    """A directed relationship between two knowledge graph nodes."""
    __tablename__ = "knowledge_edges"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_node_id = Column(Integer, ForeignKey("knowledge_nodes.id", ondelete="CASCADE"),
                            nullable=False, index=True)
    target_node_id = Column(Integer, ForeignKey("knowledge_nodes.id", ondelete="CASCADE"),
                            nullable=False, index=True)
    relation = Column(String(128), nullable=False)
    # appears_in | references | linked_to | responsible_for | part_of | impacts
    weight = Column(Float, default=1.0)
    source_document_id = Column(Integer, ForeignKey("documents.id", ondelete="SET NULL"),
                                nullable=True)
    metadata_json = Column(Text, default="{}")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_edge_source", "source_node_id", "relation"),
        Index("idx_edge_target", "target_node_id", "relation"),
        UniqueConstraint("source_node_id", "target_node_id", "relation",
                         name="uq_knowledge_edge"),
    )

    source_node = relationship("KnowledgeNode", foreign_keys=[source_node_id],
                               back_populates="edges_from", lazy="selectin")
    target_node = relationship("KnowledgeNode", foreign_keys=[target_node_id],
                               back_populates="edges_to", lazy="selectin")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "sourceNodeId": self.source_node_id,
            "targetNodeId": self.target_node_id,
            "relation": self.relation,
            "weight": self.weight,
            "sourceDocumentId": self.source_document_id,
            "metadata": json.loads(self.metadata_json) if self.metadata_json else {},
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# PILLAR 9 — DOCUMENT VERSION INTELLIGENCE
# ═══════════════════════════════════════════════════════════════════════════════

class DocumentVersion(Base):
    """Track document revisions, amendments, and superseded versions."""
    __tablename__ = "document_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"),
                         nullable=False, index=True)
    version_number = Column(String(32), nullable=False)  # "1.0", "2.0", "2.1"
    version_label = Column(String(255), default="")       # "Original", "Amendment 3"
    file_path = Column(String(512), default="")
    file_hash = Column(String(64), default="")
    file_size = Column(Integer, nullable=True)
    change_summary = Column(Text, default="")
    is_superseded = Column(Boolean, default=False)
    superseded_by_version = Column(String(32), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("document_id", "version_number", name="uq_doc_version"),
        Index("idx_doc_version_active", "document_id", "is_superseded"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "documentId": self.document_id,
            "versionNumber": self.version_number,
            "versionLabel": self.version_label,
            "filePath": self.file_path,
            "fileHash": self.file_hash,
            "fileSize": self.file_size,
            "changeSummary": self.change_summary,
            "isSuperseded": self.is_superseded,
            "supersededByVersion": self.superseded_by_version,
            "createdBy": self.created_by,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# PILLAR 10 — AGENT FRAMEWORK
# ═══════════════════════════════════════════════════════════════════════════════

class Agent(Base):
    """An AI agent definition with its configuration and tool bindings."""
    __tablename__ = "agents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(String(128), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    agent_type = Column(String(64), nullable=False, index=True)
    # policy | engineering | compliance | project | research | procurement | hr | operations
    description = Column(Text, default="")
    system_prompt = Column(Text, default="")
    model_id = Column(String(255), default="")
    provider_id = Column(String(128), default="")
    temperature = Column(Float, default=0.7)
    max_tokens = Column(Integer, default=4096)
    allow_delegation = Column(Boolean, default=False)
    allowed_tools_json = Column(Text, default="[]")  # JSON array of tool names
    config_json = Column(Text, default="{}")
    is_active = Column(Boolean, default=True)
    owner_role = Column(String(64), default="admin")
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    executions = relationship("AgentExecution", back_populates="agent", lazy="selectin")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "agentId": self.agent_id,
            "name": self.name,
            "agentType": self.agent_type,
            "description": self.description,
            "systemPrompt": self.system_prompt,
            "modelId": self.model_id,
            "providerId": self.provider_id,
            "temperature": self.temperature,
            "maxTokens": self.max_tokens,
            "allowDelegation": self.allow_delegation,
            "allowedTools": json.loads(self.allowed_tools_json) if self.allowed_tools_json else [],
            "config": json.loads(self.config_json) if self.config_json else {},
            "isActive": self.is_active,
            "ownerRole": self.owner_role,
            "createdBy": self.created_by,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }


class AgentExecution(Base):
    """Records a single agent run — its inputs, outputs, and tool calls."""
    __tablename__ = "agent_executions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(Integer, ForeignKey("agents.id", ondelete="CASCADE"),
                      nullable=False, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id", ondelete="SET NULL"),
                        nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    input_text = Column(Text, default="")
    output_text = Column(Text, default="")
    reasoning_text = Column(Text, default="")
    tool_calls_json = Column(Text, default="[]")
    status = Column(String(32), default="running")  # running | completed | failed | needs_review
    duration_ms = Column(Integer, nullable=True)
    token_count = Column(Integer, nullable=True)
    cost = Column(Float, nullable=True)
    error_message = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_agent_exec_user", "user_id"),
        Index("idx_agent_exec_status", "status"),
    )

    agent = relationship("Agent", back_populates="executions")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "agentId": self.agent_id,
            "sessionId": self.session_id,
            "userId": self.user_id,
            "inputText": self.input_text,
            "outputText": self.output_text,
            "reasoningText": self.reasoning_text,
            "toolCalls": json.loads(self.tool_calls_json) if self.tool_calls_json else [],
            "status": self.status,
            "durationMs": self.duration_ms,
            "tokenCount": self.token_count,
            "cost": self.cost,
            "errorMessage": self.error_message,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "completedAt": self.completed_at.isoformat() if self.completed_at else None,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# PILLAR 11 — HUMAN REVIEW WORKFLOWS
# ═══════════════════════════════════════════════════════════════════════════════

class HumanReview(Base):
    """A human review task on an AI-generated output."""
    __tablename__ = "human_reviews"

    id = Column(Integer, primary_key=True, autoincrement=True)
    review_type = Column(String(64), nullable=False, index=True)
    # summary | decision | report | policy_output | extraction | classification | agent_output
    entity_type = Column(String(64), nullable=False)  # doc_analysis | agent_execution | message
    entity_id = Column(Integer, nullable=False)
    content_before = Column(Text, default="")
    content_after = Column(Text, default="")
    status = Column(String(32), default="pending")  # pending | approved | rejected | changes_requested
    reviewer_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    review_comment = Column(Text, default="")
    approved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_review_entity", "entity_type", "entity_id"),
        Index("idx_review_status", "status"),
        Index("idx_review_reviewer", "reviewer_id"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "reviewType": self.review_type,
            "entityType": self.entity_type,
            "entityId": self.entity_id,
            "contentBefore": self.content_before,
            "contentAfter": self.content_after,
            "status": self.status,
            "reviewerId": self.reviewer_id,
            "reviewComment": self.review_comment,
            "approvedAt": self.approved_at.isoformat() if self.approved_at else None,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# PILLAR 12 — PROMPT GOVERNANCE
# ═══════════════════════════════════════════════════════════════════════════════

class PromptTemplate(Base):
    """Version-controlled prompt templates with governance workflow.

    Prompts are stored in the database — never in code.
    Changes require approval, are versioned, and fully auditable.
    """
    __tablename__ = "prompt_templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    template_id = Column(String(128), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, default="")
    task_type = Column(String(64), nullable=False, index=True)
    # chat | summary | extraction | classification | comparison | diagram | code | custom
    current_version = Column(Integer, default=1)
    owner = Column(String(128), default="")
    department = Column(String(64), default="")
    approval_status = Column(String(32), default="draft")
    # draft | pending_approval | approved | rejected | deprecated
    effective_date = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    versions = relationship("PromptTemplateVersion", back_populates="template",
                            lazy="selectin", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_prompt_task_type", "task_type", "is_active"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "templateId": self.template_id,
            "name": self.name,
            "description": self.description,
            "taskType": self.task_type,
            "currentVersion": self.current_version,
            "owner": self.owner,
            "department": self.department,
            "approvalStatus": self.approval_status,
            "effectiveDate": self.effective_date.isoformat() if self.effective_date else None,
            "isActive": self.is_active,
            "createdBy": self.created_by,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
            "versions": [v.to_dict() for v in self.versions] if self.versions else [],
        }


class PromptTemplateVersion(Base):
    """A single version of a prompt template."""
    __tablename__ = "prompt_template_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    template_id = Column(Integer, ForeignKey("prompt_templates.id", ondelete="CASCADE"),
                         nullable=False, index=True)
    version = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    change_notes = Column(Text, default="")
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    template = relationship("PromptTemplate", back_populates="versions")

    __table_args__ = (
        UniqueConstraint("template_id", "version", name="uq_prompt_version"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "templateId": self.template_id,
            "version": self.version,
            "content": self.content,
            "changeNotes": self.change_notes,
            "approvedBy": self.approved_by,
            "approvedAt": self.approved_at.isoformat() if self.approved_at else None,
            "createdBy": self.created_by,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# PILLAR 13 — MODEL EVALUATION FRAMEWORK
# ═══════════════════════════════════════════════════════════════════════════════

class BenchmarkRun(Base):
    """A batch model evaluation run."""
    __tablename__ = "benchmark_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_name = Column(String(255), nullable=False)
    description = Column(Text, default="")
    model_id = Column(String(255), nullable=False)
    provider_id = Column(String(128), nullable=False)
    dataset_name = Column(String(255), default="")
    total_queries = Column(Integer, default=0)
    successful_queries = Column(Integer, default=0)
    status = Column(String(32), default="pending")  # pending | running | completed | failed
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    results = relationship("BenchmarkResult", back_populates="run", lazy="selectin",
                           cascade="all, delete-orphan")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "runName": self.run_name,
            "description": self.description,
            "modelId": self.model_id,
            "providerId": self.provider_id,
            "datasetName": self.dataset_name,
            "totalQueries": self.total_queries,
            "successfulQueries": self.successful_queries,
            "status": self.status,
            "startedAt": self.started_at.isoformat() if self.started_at else None,
            "completedAt": self.completed_at.isoformat() if self.completed_at else None,
            "createdBy": self.created_by,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }


class BenchmarkResult(Base):
    """Individual evaluation result within a benchmark run."""
    __tablename__ = "benchmark_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(Integer, ForeignKey("benchmark_runs.id", ondelete="CASCADE"),
                    nullable=False, index=True)
    query = Column(Text, nullable=False)
    expected_output = Column(Text, default="")
    actual_output = Column(Text, default="")
    accuracy_score = Column(Float, nullable=True)
    citation_quality = Column(Float, nullable=True)
    hallucination_rate = Column(Float, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    token_count = Column(Integer, nullable=True)
    cost = Column(Float, nullable=True)
    success = Column(Boolean, default=True)
    error_message = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    run = relationship("BenchmarkRun", back_populates="results")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "runId": self.run_id,
            "query": self.query,
            "expectedOutput": self.expected_output,
            "actualOutput": self.actual_output,
            "accuracyScore": self.accuracy_score,
            "citationQuality": self.citation_quality,
            "hallucinationRate": self.hallucination_rate,
            "latencyMs": self.latency_ms,
            "tokenCount": self.token_count,
            "cost": self.cost,
            "success": self.success,
            "errorMessage": self.error_message,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# PILLAR 14 — COST GOVERNANCE
# ═══════════════════════════════════════════════════════════════════════════════

class CostRecord(Base):
    """Per-request cost tracking for AI operations.

    Enables cost attribution by provider, department, project, and user.
    """
    __tablename__ = "cost_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_type = Column(String(32), nullable=False, index=True)
    # message | agent_execution | analysis | benchmark | embedding
    source_id = Column(Integer, nullable=True)
    provider_id = Column(String(128), nullable=False, index=True)
    model_id = Column(String(255), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    department = Column(String(64), default="")
    tokens_input = Column(Integer, default=0)
    tokens_output = Column(Integer, default=0)
    tokens_total = Column(Integer, default=0)
    cost_per_token = Column(Float, default=0.0)
    total_cost = Column(Float, default=0.0)
    currency = Column(String(8), default="USD")
    duration_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_cost_provider", "provider_id", "created_at"),
        Index("idx_cost_user", "user_id", "created_at"),
        Index("idx_cost_department", "department", "created_at"),
        Index("idx_cost_project", "project_id", "created_at"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "sourceType": self.source_type,
            "sourceId": self.source_id,
            "providerId": self.provider_id,
            "modelId": self.model_id,
            "userId": self.user_id,
            "projectId": self.project_id,
            "department": self.department,
            "tokensInput": self.tokens_input,
            "tokensOutput": self.tokens_output,
            "tokensTotal": self.tokens_total,
            "costPerToken": self.cost_per_token,
            "totalCost": self.total_cost,
            "currency": self.currency,
            "durationMs": self.duration_ms,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }


class BudgetAlert(Base):
    """Budget threshold configuration and alerts for cost governance."""
    __tablename__ = "budget_alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scope_type = Column(String(32), nullable=False, index=True)
    # department | project | user | global
    scope_id = Column(String(128), nullable=True)  # department code, project id, user id, or '*'
    budget_amount = Column(Float, nullable=False)
    currency = Column(String(8), default="USD")
    period = Column(String(16), default="monthly")  # daily | weekly | monthly | quarterly | yearly
    current_spend = Column(Float, default=0.0)
    alert_threshold_pct = Column(Float, default=80.0)  # Alert at 80% of budget
    is_active = Column(Boolean, default=True)
    last_alert_sent_at = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("scope_type", "scope_id", "period", name="uq_budget_scope"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "scopeType": self.scope_type,
            "scopeId": self.scope_id,
            "budgetAmount": self.budget_amount,
            "currency": self.currency,
            "period": self.period,
            "currentSpend": self.current_spend,
            "alertThresholdPct": self.alert_threshold_pct,
            "isActive": self.is_active,
            "lastAlertSentAt": self.last_alert_sent_at.isoformat() if self.last_alert_sent_at else None,
            "createdBy": self.created_by,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# PILLAR 15 — TRUST & CONFIDENCE SCORING
# ═══════════════════════════════════════════════════════════════════════════════

class ConfidenceScore(Base):
    """Per-response trust and confidence scoring.

    Every AI response receives a confidence score based on:
    - Citation quality and coverage
    - Retrieval relevance scores
    - Model confidence (logprobs where available)
    - Source agreement / consistency
    """
    __tablename__ = "confidence_scores"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_type = Column(String(32), nullable=False, index=True)
    # message | agent_execution | analysis | summary
    source_id = Column(Integer, nullable=False)

    # Overall score (0.0 - 1.0)
    overall_score = Column(Float, nullable=False, default=0.0)

    # Component scores
    citation_coverage = Column(Float, nullable=True)     # What fraction of claims have citations
    retrieval_relevance = Column(Float, nullable=True)   # Avg similarity score of retrieved chunks
    model_confidence = Column(Float, nullable=True)       # Model's own confidence if available
    source_agreement = Column(Float, nullable=True)       # Cross-source consistency
    reasoning_coherence = Column(Float, nullable=True)    # Logical flow quality

    # Warning flags
    limited_evidence = Column(Boolean, default=False)
    contradictory_sources = Column(Boolean, default=False)
    low_model_confidence = Column(Boolean, default=False)

    details_json = Column(Text, default="{}")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("source_type", "source_id", name="uq_confidence_source"),
        Index("idx_confidence_score", "overall_score"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "sourceType": self.source_type,
            "sourceId": self.source_id,
            "overallScore": self.overall_score,
            "citationCoverage": self.citation_coverage,
            "retrievalRelevance": self.retrieval_relevance,
            "modelConfidence": self.model_confidence,
            "sourceAgreement": self.source_agreement,
            "reasoningCoherence": self.reasoning_coherence,
            "limitedEvidence": self.limited_evidence,
            "contradictorySources": self.contradictory_sources,
            "lowModelConfidence": self.low_model_confidence,
            "details": json.loads(self.details_json) if self.details_json else {},
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# PILLAR 17 — SECURITY & GOVERNANCE (Expanded)
# ═══════════════════════════════════════════════════════════════════════════════

class DepartmentRestriction(Base):
    """Department-level restrictions on provider/model access."""
    __tablename__ = "department_restrictions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    department = Column(String(64), nullable=False, index=True)
    restriction_type = Column(String(32), nullable=False)  # provider | model | task
    restriction_id = Column(String(128), nullable=False)   # provider_id | model_id | task_type
    is_allowed = Column(Boolean, default=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("department", "restriction_type", "restriction_id",
                         name="uq_dept_restriction"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "department": self.department,
            "restrictionType": self.restriction_type,
            "restrictionId": self.restriction_id,
            "isAllowed": self.is_allowed,
            "createdBy": self.created_by,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# PILLAR 20 — FULL AUDITABILITY (Interaction Audit Trail)
# ═══════════════════════════════════════════════════════════════════════════════

class InteractionAudit(Base):
    """Complete record of every AI interaction for compliance and investigations.

    Captures: Model, Provider, Prompt, Retrieved Chunks, Reasoning,
    Citations, Quotations, Response, Duration, Token Usage, Cost, User, Department.
    """
    __tablename__ = "interaction_audits"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("sessions.id", ondelete="SET NULL"),
                        nullable=True, index=True)
    message_id = Column(Integer, ForeignKey("messages.id", ondelete="SET NULL"),
                        nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    department = Column(String(64), default="")

    # Request details
    prompt_text = Column(Text, default="")
    system_prompt = Column(Text, default="")
    prompt_template_version = Column(Integer, nullable=True)

    # AI details
    provider_id = Column(String(128), nullable=False, index=True)
    model_id = Column(String(255), nullable=False)
    vendor = Column(String(64), default="")

    # Response details
    response_text = Column(Text, default="")
    reasoning_text = Column(Text, default="")
    citations_json = Column(Text, default="[]")
    quotations_json = Column(Text, default="[]")

    # Retrieval details
    retrieved_chunks_json = Column(Text, default="[]")
    retrieval_strategy = Column(String(32), default="vector")  # vector | hybrid | kg | keyword

    # Performance
    duration_ms = Column(Integer, nullable=True)
    tokens_input = Column(Integer, nullable=True)
    tokens_output = Column(Integer, nullable=True)
    tokens_total = Column(Integer, nullable=True)
    cost = Column(Float, nullable=True)

    # Result
    confidence_score = Column(Float, nullable=True)
    human_reviewed = Column(Boolean, default=False)
    review_status = Column(String(32), default="")  # approved | rejected | not_reviewed
    error_message = Column(Text, default="")

    # Immutable timestamp
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_audit_user_time", "user_id", "created_at"),
        Index("idx_audit_provider_time", "provider_id", "created_at"),
        Index("idx_audit_model_time", "model_id", "created_at"),
        Index("idx_audit_department_time", "department", "created_at"),
        Index("idx_audit_session", "session_id"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "sessionId": self.session_id,
            "messageId": self.message_id,
            "userId": self.user_id,
            "department": self.department,
            "promptText": self.prompt_text,
            "systemPrompt": self.system_prompt,
            "promptTemplateVersion": self.prompt_template_version,
            "providerId": self.provider_id,
            "modelId": self.model_id,
            "vendor": self.vendor,
            "responseText": self.response_text,
            "reasoningText": self.reasoning_text,
            "citations": json.loads(self.citations_json) if self.citations_json else [],
            "quotations": json.loads(self.quotations_json) if self.quotations_json else [],
            "retrievedChunks": json.loads(self.retrieved_chunks_json) if self.retrieved_chunks_json else [],
            "retrievalStrategy": self.retrieval_strategy,
            "durationMs": self.duration_ms,
            "tokensInput": self.tokens_input,
            "tokensOutput": self.tokens_output,
            "tokensTotal": self.tokens_total,
            "cost": self.cost,
            "confidenceScore": self.confidence_score,
            "humanReviewed": self.human_reviewed,
            "reviewStatus": self.review_status,
            "errorMessage": self.error_message,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }
