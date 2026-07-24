"""
agent_runtime_service.py — DocTel Multi-Agent Runtime

Coordinates multiple AI agents for collaborative knowledge processing.

Architecture:

  User Question
    ↓
  AgentCoordinator
    ├─ Intent Analysis
    ├─ Agent Selection
    ├─ Agent Execution
    │   ├─ Agent A (e.g. Retrieval Agent)  ─── stores findings in memory
    │   ├─ Agent B (e.g. Graph Agent)       ─── stores findings in memory
    │   ├─ Agent C (e.g. Policy Agent)      ─── stores findings in memory
    │   └─ Agent D (e.g. Meeting Agent)     ─── stores findings in memory
    └─ Evidence Merge
    ↓
  Merged Evidence Bundle
    ↓
  Response Strategy → Final Answer

Agents share findings via AgentMemoryService.
The Coordinator merges all evidence into a single AgentEvidenceBundle.
"""

from __future__ import annotations

import json
import logging
import time
from enum import Enum
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enterprise_models import Agent, AgentExecution, AgentExecutionPlan
from app.services.agent_memory_service import AgentMemoryService, MemoryType
from app.services.tool_execution_service import EvidenceBundle, ToolResult

logger = logging.getLogger(__name__)


# ── Agent Definitions ─────────────────────────────────────────────────────────


class AgentType(str, Enum):
    """Agent type identifiers used by the coordinator."""
    RETRIEVAL_AGENT = "retrieval_agent"
    GRAPH_AGENT = "graph_agent"
    ASSET_AGENT = "asset_agent"
    MEDIA_AGENT = "media_agent"
    WORKFLOW_AGENT = "workflow_agent"
    MEETING_AGENT = "meeting_agent"
    RISK_AGENT = "risk_agent"
    REPORTING_AGENT = "reporting_agent"
    POLICY_AGENT = "policy_agent"
    COMPARISON_AGENT = "comparison_agent"
    ENTITY_AGENT = "entity_agent"
    SUMMARY_AGENT = "summary_agent"


# ── Agent Evidence Bundle ─────────────────────────────────────────────────────


class AgentEvidenceBundle:
    """Merged evidence from multiple collaborative agents.

    Each agent contributes structured findings.
    The coordinator merges these into a unified bundle.
    """

    def __init__(self):
        self.agent_results: list[AgentResult] = []
        self.merged_entities: list[str] = []
        self.merged_actions: list[dict[str, Any]] = []
        self.merged_decisions: list[dict[str, Any]] = []
        self.merged_risks: list[dict[str, Any]] = []
        self.merged_workflows: list[dict[str, Any]] = []
        self.merged_summaries: list[str] = []
        self.execution_summary: str = ""
        self.total_duration_ms: float = 0.0

    def add_agent_result(self, result: AgentResult) -> None:
        """Record an agent's result and merge its findings."""
        self.agent_results.append(result)
        self.total_duration_ms += result.duration_ms

        # Merge findings
        if result.entities:
            for e in result.entities:
                if e not in self.merged_entities:
                    self.merged_entities.append(e)
        if result.actions:
            self.merged_actions.extend(result.actions)
        if result.decisions:
            self.merged_decisions.extend(result.decisions)
        if result.risks:
            self.merged_risks.extend(result.risks)
        if result.workflows:
            self.merged_workflows.extend(result.workflows)
        if result.summary:
            self.merged_summaries.append(result.summary)

    def build_summary(self) -> str:
        """Build a consolidated human-readable summary of all agent work."""
        parts = [f"# Agent Execution Summary: {len(self.agent_results)} agents"]

        for ar in self.agent_results:
            parts.append(f"\n## {ar.agent_type.value} ({ar.status})")
            parts.append(f"Duration: {ar.duration_ms:.0f}ms")
            if ar.summary:
                parts.append(ar.summary)
            if ar.key_findings:
                parts.extend(f"- {f}" for f in ar.key_findings)

        if self.merged_entities:
            parts.append(f"\n## Entities ({len(self.merged_entities)})")
            parts.append(", ".join(self.merged_entities))

        if self.merged_actions:
            parts.append(f"\n## Actions ({len(self.merged_actions)})")
            for a in self.merged_actions:
                parts.append(f"- {a.get('action', '')} [{a.get('owner', 'N/A')}]")

        if self.merged_decisions:
            parts.append(f"\n## Decisions ({len(self.merged_decisions)})")
            for d in self.merged_decisions:
                parts.append(f"- {d.get('decision', '')}")

        if self.merged_risks:
            parts.append(f"\n## Risks ({len(self.merged_risks)})")
            for r in self.merged_risks:
                parts.append(f"- {r.get('risk', '')} [{r.get('severity', 'N/A')}]")

        self.execution_summary = "\n".join(parts)
        return self.execution_summary

    def to_dict(self) -> dict[str, Any]:
        return {
            "agents_executed": len(self.agent_results),
            "total_duration_ms": round(self.total_duration_ms, 1),
            "merged_entities": len(self.merged_entities),
            "merged_actions": len(self.merged_actions),
            "merged_decisions": len(self.merged_decisions),
            "merged_risks": len(self.merged_risks),
            "merged_workflows": len(self.merged_workflows),
            "execution_summary": self.execution_summary,
            "agent_results": [ar.to_dict() for ar in self.agent_results],
        }


class AgentResult:
    """Result from a single agent execution."""

    def __init__(
        self,
        agent_type: AgentType,
        status: str = "completed",
        duration_ms: float = 0.0,
        summary: Optional[str] = None,
        key_findings: Optional[list[str]] = None,
        entities: Optional[list[str]] = None,
        actions: Optional[list[dict[str, Any]]] = None,
        decisions: Optional[list[dict[str, Any]]] = None,
        risks: Optional[list[dict[str, Any]]] = None,
        workflows: Optional[list[dict[str, Any]]] = None,
        evidence: Optional[EvidenceBundle] = None,
        metadata: Optional[dict[str, Any]] = None,
        error: Optional[str] = None,
    ):
        self.agent_type = agent_type
        self.status = status
        self.duration_ms = duration_ms
        self.summary = summary
        self.key_findings = key_findings or []
        self.entities = entities or []
        self.actions = actions or []
        self.decisions = decisions or []
        self.risks = risks or []
        self.workflows = workflows or []
        self.evidence = evidence
        self.metadata = metadata or {}
        self.error = error

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_type": self.agent_type.value,
            "status": self.status,
            "duration_ms": round(self.duration_ms, 1),
            "summary": self.summary,
            "key_findings": self.key_findings,
            "entities_count": len(self.entities),
            "actions_count": len(self.actions),
            "decisions_count": len(self.decisions),
            "risks_count": len(self.risks),
            "has_evidence": self.evidence is not None,
            "error": self.error,
        }


# ── Agent Registry ────────────────────────────────────────────────────────────


class AgentRegistry:
    """Registry of available agents with their descriptions and capabilities."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._agents: dict[str, dict[str, Any]] = {}

    async def load_from_db(self) -> None:
        """Load agent definitions from the Agent table (enterprise_models).
        
        Falls back to built-in defaults if the table is empty.
        """
        try:
            from sqlalchemy import select
            result = await self.db.execute(
                select(Agent).where(Agent.is_active == True)
            )
            db_agents = result.scalars().all()
            for a in db_agents:
                self._agents[a.agent_id] = a.to_dict()
        except Exception as exc:
            logger.warning("[AGENT] Failed to load agents from DB: %s", exc)

        # Always populate defaults for agents not in DB
        defaults = self._get_default_agents()
        for agent_id, config in defaults.items():
            if agent_id not in self._agents:
                self._agents[agent_id] = config

    def _get_default_agents(self) -> dict[str, dict[str, Any]]:
        """Built-in default agent definitions."""
        return {
            AgentType.RETRIEVAL_AGENT.value: {
                "agent_id": AgentType.RETRIEVAL_AGENT.value,
                "name": "Retrieval Agent",
                "agent_type": "retrieval",
                "description": "Searches document vectors and knowledge graph for relevant chunks and citations",
                "allowed_tools": ["rag_search", "knowledge_graph"],
                "system_prompt": "You are a knowledge retrieval specialist. Find the most relevant document chunks and graph nodes for the user query.",
            },
            AgentType.GRAPH_AGENT.value: {
                "agent_id": AgentType.GRAPH_AGENT.value,
                "name": "Graph Agent",
                "agent_type": "graph",
                "description": "Traverses the knowledge graph to discover entity relationships, pathways, and dependencies",
                "allowed_tools": ["knowledge_graph", "entity_extraction"],
                "system_prompt": "You are a knowledge graph analyst. Traverse the enterprise knowledge graph to discover relationships and patterns.",
            },
            AgentType.ASSET_AGENT.value: {
                "agent_id": AgentType.ASSET_AGENT.value,
                "name": "Knowledge Asset Agent",
                "agent_type": "asset",
                "description": "Discovers and organizes knowledge assets (documents, audio, video, CSV) across spaces",
                "allowed_tools": ["knowledge_asset", "knowledge_space"],
                "system_prompt": "You are a knowledge asset specialist. Find and organize knowledge assets across enterprise knowledge spaces.",
            },
            AgentType.MEDIA_AGENT.value: {
                "agent_id": AgentType.MEDIA_AGENT.value,
                "name": "Media Intelligence Agent",
                "agent_type": "media",
                "description": "Analyzes audio, video, and image assets with transcription and vision capabilities",
                "allowed_tools": ["audio_analysis", "video_analysis", "image_analysis"],
                "system_prompt": "You are a media intelligence specialist. Analyze audio recordings, video content, and images for insights.",
            },
            AgentType.WORKFLOW_AGENT.value: {
                "agent_id": AgentType.WORKFLOW_AGENT.value,
                "name": "Workflow Agent",
                "agent_type": "workflow",
                "description": "Extracts and documents business processes, workflows, and standard operating procedures",
                "allowed_tools": ["workflow_extraction", "process_diagram"],
                "system_prompt": "You are a business process analyst. Extract workflows, document process steps, and identify business rules.",
            },
            AgentType.MEETING_AGENT.value: {
                "agent_id": AgentType.MEETING_AGENT.value,
                "name": "Meeting Intelligence Agent",
                "agent_type": "meeting",
                "description": "Analyzes meeting transcripts to extract decisions, actions, risks, and follow-ups",
                "allowed_tools": ["meeting_analysis", "action_extraction", "decision_extraction"],
                "system_prompt": "You are a meeting analyst. Extract decisions, action items, risks, and follow-ups from meeting transcripts.",
            },
            AgentType.RISK_AGENT.value: {
                "agent_id": AgentType.RISK_AGENT.value,
                "name": "Risk Assessment Agent",
                "agent_type": "risk",
                "description": "Identifies and assesses operational, compliance, and security risks from enterprise content",
                "allowed_tools": ["risk_analysis", "policy_analysis"],
                "system_prompt": "You are a risk assessment specialist. Identify risks, assess likelihood and impact, and recommend mitigations.",
            },
            AgentType.REPORTING_AGENT.value: {
                "agent_id": AgentType.REPORTING_AGENT.value,
                "name": "Reporting Agent",
                "agent_type": "reporting",
                "description": "Generates structured reports, executive summaries, and management dashboards",
                "allowed_tools": ["document_summary", "report_generation", "chart"],
                "system_prompt": "You are a reporting specialist. Generate structured reports, executive summaries, and management dashboards.",
            },
            AgentType.POLICY_AGENT.value: {
                "agent_id": AgentType.POLICY_AGENT.value,
                "name": "Policy Analysis Agent",
                "agent_type": "policy",
                "description": "Analyzes policy documents for obligations, controls, compliance requirements, and governance",
                "allowed_tools": ["policy_analysis", "risk_analysis"],
                "system_prompt": "You are a policy compliance analyst. Extract obligations, controls, governance requirements, and compliance risks.",
            },
            AgentType.COMPARISON_AGENT.value: {
                "agent_id": AgentType.COMPARISON_AGENT.value,
                "name": "Comparison Agent",
                "agent_type": "comparison",
                "description": "Compares documents, policies, workflows, and systems for differences and gaps",
                "allowed_tools": ["document_compare", "entity_extraction"],
                "system_prompt": "You are a comparison analyst. Compare documents, policies, and systems to identify differences, gaps, and recommendations.",
            },
            AgentType.ENTITY_AGENT.value: {
                "agent_id": AgentType.ENTITY_AGENT.value,
                "name": "Entity Extraction Agent",
                "agent_type": "entity",
                "description": "Extracts people, systems, departments, policies, locations, and business entities from content",
                "allowed_tools": ["entity_extraction"],
                "system_prompt": "You are a knowledge extraction specialist. Extract entities, topics, systems, and relationships from enterprise content.",
            },
            AgentType.SUMMARY_AGENT.value: {
                "agent_id": AgentType.SUMMARY_AGENT.value,
                "name": "Summary Agent",
                "agent_type": "summary",
                "description": "Generates concise executive summaries and document overviews",
                "allowed_tools": ["document_summary"],
                "system_prompt": "You are an executive summarizer. Generate concise, insight-rich summaries from enterprise content.",
            },
        }

    def get_agent(self, agent_type: AgentType) -> Optional[dict[str, Any]]:
        """Get an agent definition by type."""
        return self._agents.get(agent_type.value)

    def get_all_agents(self) -> list[dict[str, Any]]:
        """Get all registered agents."""
        return list(self._agents.values())

    def get_agents_by_types(self, types: list[AgentType]) -> list[dict[str, Any]]:
        """Get agent definitions matching the given types."""
        return [self._agents[t.value] for t in types if t.value in self._agents]


# ── Intent → Agent Selection ──────────────────────────────────────────────────


# Maps user intents to the most appropriate agent types.
# The coordinator dispatches to these agents when an intent is detected.

_INTENT_AGENT_MAP: dict[str, list[AgentType]] = {
    "question_answering": [
        AgentType.RETRIEVAL_AGENT,
        AgentType.GRAPH_AGENT,
    ],
    "executive_summary": [
        AgentType.SUMMARY_AGENT,
        AgentType.ENTITY_AGENT,
    ],
    "document_analysis": [
        AgentType.SUMMARY_AGENT,
        AgentType.ENTITY_AGENT,
        AgentType.WORKFLOW_AGENT,
    ],
    "policy_review": [
        AgentType.POLICY_AGENT,
        AgentType.RISK_AGENT,
    ],
    "frs_analysis": [
        AgentType.WORKFLOW_AGENT,
        AgentType.ENTITY_AGENT,
        AgentType.COMPARISON_AGENT,
    ],
    "meeting_analysis": [
        AgentType.MEETING_AGENT,
        AgentType.MEDIA_AGENT,
    ],
    "risk_assessment": [
        AgentType.RISK_AGENT,
        AgentType.POLICY_AGENT,
    ],
    "action_extraction": [
        AgentType.MEETING_AGENT,
        AgentType.RETRIEVAL_AGENT,
    ],
    "workflow_extraction": [
        AgentType.WORKFLOW_AGENT,
        AgentType.RETRIEVAL_AGENT,
    ],
    "process_diagram": [
        AgentType.WORKFLOW_AGENT,
        AgentType.REPORTING_AGENT,
    ],
    "comparison": [
        AgentType.COMPARISON_AGENT,
        AgentType.RETRIEVAL_AGENT,
    ],
    "root_cause_analysis": [
        AgentType.RETRIEVAL_AGENT,
        AgentType.WORKFLOW_AGENT,
        AgentType.RISK_AGENT,
    ],
    "data_analysis": [
        AgentType.REPORTING_AGENT,
        AgentType.RETRIEVAL_AGENT,
    ],
    "csv_analysis": [
        AgentType.ASSET_AGENT,
        AgentType.REPORTING_AGENT,
    ],
    "database_analysis": [
        AgentType.ASSET_AGENT,
        AgentType.REPORTING_AGENT,
    ],
    "report_generation": [
        AgentType.REPORTING_AGENT,
        AgentType.SUMMARY_AGENT,
    ],
    "knowledge_discovery": [
        AgentType.GRAPH_AGENT,
        AgentType.ASSET_AGENT,
        AgentType.RETRIEVAL_AGENT,
    ],
    "image_analysis": [
        AgentType.MEDIA_AGENT,
        AgentType.ENTITY_AGENT,
    ],
    "audio_analysis": [
        AgentType.MEDIA_AGENT,
        AgentType.MEETING_AGENT,
    ],
    "video_analysis": [
        AgentType.MEDIA_AGENT,
        AgentType.MEETING_AGENT,
    ],
    "chat": [
        AgentType.RETRIEVAL_AGENT,
    ],
}


def select_agents_for_intent(intent: str) -> list[AgentType]:
    """Select the appropriate agent types for a detected intent.

    Returns agent types in execution order.
    """
    return _INTENT_AGENT_MAP.get(intent, _INTENT_AGENT_MAP["question_answering"])


# ── Agent Coordinator ─────────────────────────────────────────────────────────


class AgentCoordinator:
    """Coordinates multi-agent execution for a user query.

    Workflow:
    1. Register agents from Agent table (with fallback defaults)
    2. Select agents based on detected intent
    3. Execute each agent and collect results
    4. Store findings in agent memory
    5. Merge evidence into AgentEvidenceBundle
    6. Build execution summary
    """

    def __init__(
        self,
        db: AsyncSession,
        memory_service: Optional[AgentMemoryService] = None,
    ):
        self.db = db
        self.memory_service = memory_service or AgentMemoryService(db)
        self.registry = AgentRegistry(db)

    async def initialize(self) -> None:
        """Initialize the coordinator: load agent definitions from DB."""
        await self.registry.load_from_db()
        logger.info(
            "[COORDINATOR] Initialized with %d agents",
            len(self.registry.get_all_agents()),
        )

    async def execute_agent_plan(
        self,
        intent: str,
        user_query: str,
        session_id: Optional[int] = None,
        document_id: Optional[str] = None,
        project_ids: Optional[list[int]] = None,
        audio_transcript: Optional[str] = None,
        execution_id: Optional[int] = None,
    ) -> AgentEvidenceBundle:
        """Execute the agent plan for a given intent and query.

        This is the main entry point for the multi-agent runtime.
        It selects agents, executes them, merges evidence, and stores
        findings in agent memory.

        Args:
            intent: Detected knowledge intent.
            user_query: The original user question.
            session_id: Optional session ID for memory scoping.
            document_id: Optional document ID for scoped retrieval.
            project_ids: Optional project IDs for scoped retrieval.
            audio_transcript: Optional audio transcript for media analysis.
            execution_id: Optional agent execution ID for tracking.

        Returns:
            AgentEvidenceBundle with merged findings from all agents.
        """
        start_time = time.time()
        bundle = AgentEvidenceBundle()

        # 1. Select agents for this intent
        agent_types = select_agents_for_intent(intent)
        logger.info(
            "[COORDINATOR] Intent=%s → %d agents: %s",
            intent, len(agent_types),
            [t.value for t in agent_types],
        )

        # 2. Execute each agent
        for agent_type in agent_types:
            agent_start = time.time()
            agent_config = self.registry.get_agent(agent_type)
            if agent_config is None:
                logger.warning("[COORDINATOR] Agent %s not found, skipping", agent_type.value)
                continue

            try:
                result = await self._execute_single_agent(
                    agent_type=agent_type,
                    agent_config=agent_config,
                    user_query=user_query,
                    session_id=session_id,
                    document_id=document_id,
                    project_ids=project_ids,
                    audio_transcript=audio_transcript,
                    execution_id=execution_id,
                )
            except Exception as exc:
                logger.error("[COORDINATOR] Agent %s failed: %s", agent_type.value, exc)
                # Rollback DB to prevent PostgreSQL transaction abort from propagating
                try:
                    await self.db.rollback()
                except Exception:
                    pass
                result = AgentResult(
                    agent_type=agent_type,
                    status="failed",
                    duration_ms=(time.time() - agent_start) * 1000,
                    error=str(exc),
                )

            # Store agent findings in memory
            if session_id is not None and result.status == "completed":
                await self._store_agent_findings(result, session_id, execution_id)

            # Merge into bundle
            bundle.add_agent_result(result)

        # 3. Build execution summary
        bundle.total_duration_ms = (time.time() - start_time) * 1000
        bundle.build_summary()

        logger.info(
            "[COORDINATOR] Complete: %d agents in %.0fms",
            len(bundle.agent_results), bundle.total_duration_ms,
        )

        return bundle

    async def _execute_single_agent(
        self,
        agent_type: AgentType,
        agent_config: dict[str, Any],
        user_query: str,
        session_id: Optional[int] = None,
        document_id: Optional[str] = None,
        project_ids: Optional[list[int]] = None,
        audio_transcript: Optional[str] = None,
        execution_id: Optional[int] = None,
    ) -> AgentResult:
        """Execute a single agent by type.

        Each agent type knows how to perform its task.
        Agents use the existing tool execution infrastructure.
        """
        agent_start = time.time()
        allowed_tools = agent_config.get("allowed_tools", [])
        logger.debug(
            "[COORDINATOR] Executing %s with tools: %s",
            agent_type.value, allowed_tools,
        )

        key_findings: list[str] = []
        entities: list[str] = []
        actions: list[dict[str, Any]] = []
        decisions: list[dict[str, Any]] = []
        risks: list[dict[str, Any]] = []
        workflows: list[dict[str, Any]] = []
        summary: Optional[str] = None
        evidence: Optional[EvidenceBundle] = None

        # ── RETRIEVAL AGENT ─────────────────────────────────────────────
        if agent_type == AgentType.RETRIEVAL_AGENT:
            try:
                from app.services.tool_planner_service import (
                    ExecutionPlan, ExecutionObserver, ToolType,
                )
                from app.services.tool_execution_service import (
                    execute_plan as execute_tool_plan,
                )

                observer = ExecutionObserver()
                plan = ExecutionPlan(
                    intent="question_answering",
                    tools=[
                        {"tool": ToolType.RAG_SEARCH, "optional": False},
                    ],
                    estimated_steps=2,
                    strategy_summary="RAG retrieval for question answering",
                    render_hint="narrative",
                    citation_mode="full",
                )

                evidence = await execute_tool_plan(
                    plan=plan,
                    user_query=user_query,
                    db=self.db,
                    observer=observer,
                    project_ids=project_ids,
                    document_id=document_id,
                )
                if evidence:
                    entities = evidence.entities
                    key_findings.append(
                        f"Retrieved {len(evidence.sources)} sources from knowledge base"
                    )
                    if evidence.risks:
                        key_findings.append(
                            f"Identified {len(evidence.risks)} risks in retrieved content"
                        )
            except Exception as exc:
                logger.warning("[RETRIEVAL_AGENT] Failed: %s", exc)
                return AgentResult(
                    agent_type=agent_type, status="failed",
                    duration_ms=(time.time() - agent_start) * 1000,
                    error=str(exc),
                )

        # ── GRAPH AGENT ─────────────────────────────────────────────────
        elif agent_type == AgentType.GRAPH_AGENT:
            try:
                from app.services.knowledge_graph_service import KnowledgeGraphService

                kg = KnowledgeGraphService(self.db)

                # Search graph for entities matching the query
                entities_result = await kg.find_assets_by_entity(user_query, limit=10)
                if entities_result:
                    entities = list(set(
                        e.get("label", str(e)) for e in entities_result
                    ))
                    key_findings.append(
                        f"Discovered {len(entities)} graph entities related to query"
                    )

                # Find related entities
                related = await kg.find_related_entities(
                    entity_name=user_query, limit=5, max_depth=1
                )
                if related:
                    key_findings.append(
                        f"Found {len(related)} related assets in knowledge graph"
                    )

                # Explore graph for context
                explore = await kg.explore_graph(limit=20)
                if explore.get("nodes"):
                    key_findings.append(
                        f"Graph contains {explore['total_nodes']} nodes and "
                        f"{explore['total_edges_shown']} edges"
                    )

            except Exception as exc:
                logger.warning("[GRAPH_AGENT] Failed: %s", exc)
                return AgentResult(
                    agent_type=agent_type, status="failed",
                    duration_ms=(time.time() - agent_start) * 1000,
                    error=str(exc),
                )

        # ── ASSET AGENT ─────────────────────────────────────────────────
        elif agent_type == AgentType.ASSET_AGENT:
            try:
                from app.services.knowledge_asset_service import KnowledgeAssetService

                kas = KnowledgeAssetService(self.db)
                assets = await kas.search_assets(query=user_query, limit=10)
                if assets:
                    asset_names = [a.get("title", a.get("id", "Unknown")) for a in assets]
                    entities.extend(asset_names)
                    key_findings.append(
                        f"Found {len(assets)} knowledge assets matching query"
                    )

                # Also look in spaces
                try:
                    from app.services.knowledge_space_service import KnowledgeSpaceService

                    kss = KnowledgeSpaceService(self.db)
                    spaces = await kss.search_spaces(query=user_query)
                    if spaces:
                        key_findings.append(
                            f"Discovered {len(spaces)} knowledge spaces"
                        )
                except Exception:
                    pass
            except Exception as exc:
                logger.warning("[ASSET_AGENT] Failed: %s", exc)
                return AgentResult(
                    agent_type=agent_type, status="failed",
                    duration_ms=(time.time() - agent_start) * 1000,
                    error=str(exc),
                )

        # ── MEDIA AGENT ─────────────────────────────────────────────────
        elif agent_type == AgentType.MEDIA_AGENT:
            try:
                if audio_transcript:
                    from app.services.tool_execution_service import _execute_audio_analysis
                    from app.services.tool_planner_service import ExecutionObserver

                    observer = ExecutionObserver()
                    obs = await _execute_audio_analysis(audio_transcript, observer)
                    if obs.success and obs.result:
                        if isinstance(obs.result, dict):
                            summary = obs.result.get("summary", "")
                            entities.extend(obs.result.get("speakers", []))
                            entities.extend(obs.result.get("topics", []))
                            if obs.result.get("key_points"):
                                key_findings.extend(obs.result["key_points"])
                            key_findings.append("Audio recording analyzed successfully")
                else:
                    # Search for media assets
                    from app.services.knowledge_asset_service import KnowledgeAssetService
                    kas = KnowledgeAssetService(self.db)
                    media_assets = await kas.search_assets(
                        query=f"{user_query} audio video image",
                        limit=5,
                    )
                    if media_assets:
                        key_findings.append(
                            f"Found {len(media_assets)} media assets"
                        )
            except Exception as exc:
                logger.warning("[MEDIA_AGENT] Failed: %s", exc)
                return AgentResult(
                    agent_type=agent_type, status="failed",
                    duration_ms=(time.time() - agent_start) * 1000,
                    error=str(exc),
                )

        # ── MEETING AGENT ───────────────────────────────────────────────
        elif agent_type == AgentType.MEETING_AGENT:
            try:
                content = audio_transcript or user_query
                from app.services.tool_execution_service import (
                    _execute_meeting_analysis,
                )
                from app.services.tool_planner_service import ExecutionObserver

                observer = ExecutionObserver()
                obs = await _execute_meeting_analysis(content, observer)
                if obs.success and obs.result:
                    if isinstance(obs.result, dict):
                        summary = obs.result.get("summary", "")
                        decisions = [
                            {"decision": d} if isinstance(d, str) else d
                            for d in obs.result.get("decisions", [])
                        ]
                        actions_out = [
                            {"action": a} if isinstance(a, str) else a
                            for a in obs.result.get("action_items", [])
                        ]
                        risks_out = [
                            {"risk": r} if isinstance(r, str) else r
                            for r in obs.result.get("risks", [])
                        ]
                        key_findings.append("Meeting analysis complete")
                        if decisions:
                            key_findings.append(f"Extracted {len(decisions)} decisions")
                        if actions_out:
                            key_findings.append(f"Extracted {len(actions_out)} action items")
            except Exception as exc:
                logger.warning("[MEETING_AGENT] Failed: %s", exc)
                return AgentResult(
                    agent_type=agent_type, status="failed",
                    duration_ms=(time.time() - agent_start) * 1000,
                    error=str(exc),
                )

        # ── WORKFLOW AGENT ──────────────────────────────────────────────
        elif agent_type == AgentType.WORKFLOW_AGENT:
            try:
                from app.services.tool_execution_service import (
                    _execute_workflow_extraction,
                )
                from app.services.tool_planner_service import ExecutionObserver

                observer = ExecutionObserver()
                obs = await _execute_workflow_extraction(user_query, observer)
                if obs.success and obs.result:
                    if isinstance(obs.result, dict):
                        steps = obs.result.get("steps", [])
                        actors = obs.result.get("actors", [])
                        rules = obs.result.get("business_rules", [])
                        workflows.append(obs.result)
                        if steps:
                            key_findings.append(
                                f"Extracted {len(steps)} workflow steps"
                            )
                        if actors:
                            entities.extend(actors)
            except Exception as exc:
                logger.warning("[WORKFLOW_AGENT] Failed: %s", exc)
                return AgentResult(
                    agent_type=agent_type, status="failed",
                    duration_ms=(time.time() - agent_start) * 1000,
                    error=str(exc),
                )

        # ── RISK AGENT ──────────────────────────────────────────────────
        elif agent_type == AgentType.RISK_AGENT:
            try:
                from app.services.tool_execution_service import _execute_risk_analysis
                from app.services.tool_planner_service import ExecutionObserver

                observer = ExecutionObserver()
                obs = await _execute_risk_analysis(user_query, observer)
                if obs.success and obs.result:
                    if isinstance(obs.result, list):
                        risks = obs.result
                    elif isinstance(obs.result, dict):
                        risks = obs.result.get("risks", [])
                    if risks:
                        key_findings.append(f"Identified {len(risks)} risks")
            except Exception as exc:
                logger.warning("[RISK_AGENT] Failed: %s", exc)
                return AgentResult(
                    agent_type=agent_type, status="failed",
                    duration_ms=(time.time() - agent_start) * 1000,
                    error=str(exc),
                )

        # ── POLICY AGENT ────────────────────────────────────────────────
        elif agent_type == AgentType.POLICY_AGENT:
            try:
                from app.services.tool_execution_service import _execute_policy_analysis
                from app.services.tool_planner_service import ExecutionObserver

                observer = ExecutionObserver()
                obs = await _execute_policy_analysis(user_query, observer)
                if obs.success and obs.result:
                    if isinstance(obs.result, dict):
                        obligations = obs.result.get("obligations", [])
                        controls = obs.result.get("controls", [])
                        pol_risks = obs.result.get("risks", [])
                        risks.extend(
                            {"risk": r} if isinstance(r, str) else r
                            for r in pol_risks
                        )
                        if obligations:
                            key_findings.append(
                                f"Extracted {len(obligations)} policy obligations"
                            )
                        if controls:
                            key_findings.append(
                                f"Identified {len(controls)} controls"
                            )
            except Exception as exc:
                logger.warning("[POLICY_AGENT] Failed: %s", exc)
                return AgentResult(
                    agent_type=agent_type, status="failed",
                    duration_ms=(time.time() - agent_start) * 1000,
                    error=str(exc),
                )

        # ── ENTITY AGENT ────────────────────────────────────────────────
        elif agent_type == AgentType.ENTITY_AGENT:
            try:
                from app.services.tool_execution_service import _execute_entity_extraction
                from app.services.tool_planner_service import ExecutionObserver

                observer = ExecutionObserver()
                obs = await _execute_entity_extraction(user_query, observer)
                if obs.success and obs.result:
                    if isinstance(obs.result, dict):
                        entities.extend(obs.result.get("entities", []))
                        entities.extend(obs.result.get("systems", []))
                        entities.extend(obs.result.get("people", []))
                        entities.extend(obs.result.get("topics", []))
                        if entities:
                            key_findings.append(
                                f"Extracted {len(entities)} entities"
                            )
            except Exception as exc:
                logger.warning("[ENTITY_AGENT] Failed: %s", exc)
                return AgentResult(
                    agent_type=agent_type, status="failed",
                    duration_ms=(time.time() - agent_start) * 1000,
                    error=str(exc),
                )

        # ── SUMMARY AGENT ───────────────────────────────────────────────
        elif agent_type == AgentType.SUMMARY_AGENT:
            try:
                from app.services.tool_execution_service import (
                    _execute_document_summary,
                )
                from app.services.tool_planner_service import ExecutionObserver

                observer = ExecutionObserver()
                obs = await _execute_document_summary(user_query, observer)
                if obs.success and obs.result:
                    if isinstance(obs.result, dict):
                        summary = obs.result.get("overview") or obs.result.get(
                            "summary"
                        ) or obs.result.get("conclusion", "")
                        if obs.result.get("key_findings"):
                            key_findings.extend(obs.result["key_findings"])
                        if obs.result.get("systems"):
                            entities.extend(obs.result["systems"])
            except Exception as exc:
                logger.warning("[SUMMARY_AGENT] Failed: %s", exc)
                return AgentResult(
                    agent_type=agent_type, status="failed",
                    duration_ms=(time.time() - agent_start) * 1000,
                    error=str(exc),
                )

        # ── COMPARISON AGENT ────────────────────────────────────────────
        elif agent_type == AgentType.COMPARISON_AGENT:
            try:
                from app.services.knowledge_graph_service import KnowledgeGraphService

                # Use graph to find comparison candidates via entity matching
                kg = KnowledgeGraphService(self.db)
                related = await kg.find_related_entities(
                    entity_name=user_query, limit=5, max_depth=1
                )
                if related:
                    key_findings.append(
                        f"Found {len(related)} related assets for comparison"
                    )
            except Exception as exc:
                logger.warning("[COMPARISON_AGENT] Failed: %s", exc)
                return AgentResult(
                    agent_type=agent_type, status="failed",
                    duration_ms=(time.time() - agent_start) * 1000,
                    error=str(exc),
                )

        # ── REPORTING AGENT ─────────────────────────────────────────────
        elif agent_type == AgentType.REPORTING_AGENT:
            # Reporting agent defers actual report generation to the LLM call
            # It just sets up context for the report format
            key_findings.append("Report generation context prepared")
            summary = "Ready for structured report output"

        duration_ms = (time.time() - agent_start) * 1000
        return AgentResult(
            agent_type=agent_type,
            status="completed",
            duration_ms=duration_ms,
            summary=summary,
            key_findings=key_findings,
            entities=entities,
            actions=actions,
            decisions=decisions,
            risks=risks,
            workflows=workflows,
            evidence=evidence,
            metadata={
                "allowed_tools": allowed_tools,
                "entity_count": len(entities),
                "finding_count": len(key_findings),
            },
        )

    async def _store_agent_findings(
        self,
        result: AgentResult,
        session_id: int,
        execution_id: Optional[int] = None,
    ) -> None:
        """Store agent findings in persistent memory."""
        try:
            exec_id = execution_id or -1

            # Store summary
            if result.summary:
                await self.memory_service.store_memory(
                    agent_execution_id=exec_id,
                    key=f"{result.agent_type.value}_summary",
                    value={"summary": result.summary},
                    memory_type=MemoryType.EPISODIC.value,
                    session_id=session_id,
                )

            # Store entities
            if result.entities:
                await self.memory_service.store_memory(
                    agent_execution_id=exec_id,
                    key=f"{result.agent_type.value}_entities",
                    value={"entities": result.entities},
                    memory_type=MemoryType.SEMANTIC.value,
                    session_id=session_id,
                )

            # Store key findings
            if result.key_findings:
                await self.memory_service.store_memory(
                    agent_execution_id=exec_id,
                    key=f"{result.agent_type.value}_findings",
                    value={"findings": result.key_findings},
                    memory_type=MemoryType.EPISODIC.value,
                    session_id=session_id,
                )

            # Store actions
            if result.actions:
                await self.memory_service.store_memory(
                    agent_execution_id=exec_id,
                    key=f"{result.agent_type.value}_actions",
                    value={"actions": result.actions},
                    memory_type=MemoryType.EPISODIC.value,
                    session_id=session_id,
                )

            # Promote working memories
            await self.memory_service.promote_session_memories(
                session_id=session_id,
                target_type=MemoryType.EPISODIC.value,
            )

        except Exception as exc:
            logger.warning(
                "[COORDINATOR] Failed to store %s findings: %s",
                result.agent_type.value, exc,
            )
            # Rollback DB to prevent PostgreSQL transaction abort from propagating
            try:
                await self.db.rollback()
            except Exception:
                pass

    async def get_session_memory_context(
        self,
        session_id: int,
        max_tokens: int = 2000,
    ) -> str:
        """Build a memory context string for LLM prompt injection.

        Returns a compact summary of all memories for this session.
        """
        return await self.memory_service.build_memory_context(
            session_id=session_id,
            max_tokens=max_tokens,
        )

    async def build_memory_prompt_section(
        self,
        session_id: Optional[int] = None,
        audio_transcript: Optional[str] = None,
    ) -> str:
        """Build a complete memory context section for the system prompt.

        Includes:
        - Agent memory from past sessions
        - Audio transcript context (if active)
        - Active session state
        """
        parts = []

        # 1. Agent memory
        if session_id is not None:
            memory_context = await self.get_session_memory_context(session_id)
            if memory_context:
                parts.append(memory_context)

        # 2. Audio transcript context
        if audio_transcript:
            transcript_preview = audio_transcript[:1500]
            if len(audio_transcript) > 1500:
                transcript_preview += "\n...[transcript truncated]"
            parts.append(
                f"[ACTIVE AUDIO RECORDING]\n"
                f"The user has loaded an audio recording transcript into the session.\n"
                f"Full transcript is available for detailed questions.\n"
                f"Preview:\n{transcript_preview}"
            )

        return "\n\n".join(parts)


# ── Convenience Wrapper ───────────────────────────────────────────────────────


async def execute_agent_plan(
    db: AsyncSession,
    intent: str,
    user_query: str,
    session_id: Optional[int] = None,
    document_id: Optional[str] = None,
    project_ids: Optional[list[int]] = None,
    audio_transcript: Optional[str] = None,
) -> AgentEvidenceBundle:
    """Convenience function to create a coordinator and execute an agent plan.

    Usage:
        bundle = await execute_agent_plan(
            db=db,
            intent="meeting_analysis",
            user_query="Summarize this meeting",
            session_id=123,
            audio_transcript="... transcript text ...",
        )
    """
    coordinator = AgentCoordinator(db)
    await coordinator.initialize()
    return await coordinator.execute_agent_plan(
        intent=intent,
        user_query=user_query,
        session_id=session_id,
        document_id=document_id,
        project_ids=project_ids,
        audio_transcript=audio_transcript,
    )
