"""
workflow_engine_service.py — DocTel Autonomous Workflow Engine

Architecture:

  User Objective (e.g. "Review CRM Policy")
    ↓
  Workflow Engine
    ├─ resolve_workflow() — classify objective → workflow type
    ├─ build_execution_plan() — select agents + tools + assets
    ├─ execute_workflow() — launch agents, collect evidence
    ├─ generate_deliverables() — LLM-driven report content
    ├─ persist_to_db() — survive restarts, multi-worker
    └─ store_results() — persist to AgentMemory + DB
    ↓
  Deliverables (Executive Report, Risk Register, Action Register, etc.)
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# ── Workflow Types ────────────────────────────────────────────────────────────


class WorkflowType(str, Enum):
    """Supported autonomous workflow types."""
    POLICY_REVIEW = "policy_review"
    MEETING_REVIEW = "meeting_review"
    FRS_REVIEW = "frs_review"
    PROJECT_HEALTH_CHECK = "project_health_check"
    RISK_ASSESSMENT = "risk_assessment"
    COMPLIANCE_REVIEW = "compliance_review"
    KNOWLEDGE_DISCOVERY = "knowledge_discovery"
    EXECUTIVE_BRIEFING = "executive_briefing"
    CUSTOM = "custom"


# ── Workflow Step ──────────────────────────────────────────────────────────────


class WorkflowStep:
    """A single step in a workflow execution plan."""

    def __init__(
        self,
        step_id: int,
        agent_type: str,
        purpose: str,
        status: str = "pending",
        result: Optional[dict[str, Any]] = None,
        duration_ms: float = 0.0,
        error: Optional[str] = None,
    ):
        self.step_id = step_id
        self.agent_type = agent_type
        self.purpose = purpose
        self.status = status  # pending | running | completed | failed | skipped
        self.result = result or {}
        self.duration_ms = duration_ms
        self.error = error

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "agent_type": self.agent_type,
            "purpose": self.purpose,
            "status": self.status,
            "result": self.result,
            "duration_ms": round(self.duration_ms, 1),
            "error": self.error,
        }


# ── Workflow Definition ───────────────────────────────────────────────────────


class WorkflowDefinition:
    """Template definition for a workflow type."""

    def __init__(
        self,
        workflow_type: WorkflowType,
        name: str,
        description: str,
        objective_patterns: list[str],
        agent_plan: list[dict[str, Any]],
        expected_deliverables: list[str],
        success_criteria: list[str],
    ):
        self.workflow_type = workflow_type
        self.name = name
        self.description = description
        self.objective_patterns = objective_patterns
        self.agent_plan = agent_plan
        self.expected_deliverables = expected_deliverables
        self.success_criteria = success_criteria


# ── Built-in Workflow Definitions ────────────────────────────────────────────


_WORKFLOW_REGISTRY: dict[WorkflowType, WorkflowDefinition] = {
    WorkflowType.POLICY_REVIEW: WorkflowDefinition(
        workflow_type=WorkflowType.POLICY_REVIEW,
        name="Policy Review",
        description=(
            "Reviews a policy document against compliance requirements. "
            "Extracts obligations, controls, risks, and generates a compliance report."
        ),
        objective_patterns=[
            "review.*policy", "policy.*review", "compliance.*policy",
            "policy.*compliance", "audit.*policy", "policy.*audit",
            "governance.*policy", "policy.*governance",
        ],
        agent_plan=[
            {"agent_type": "retrieval_agent", "purpose": "Find the policy document and related content", "optional": False},
            {"agent_type": "graph_agent", "purpose": "Discover related workflows, processes, and dependencies", "optional": False},
            {"agent_type": "policy_agent", "purpose": "Analyze policy obligations, controls, and risks", "optional": False},
            {"agent_type": "risk_agent", "purpose": "Assess compliance and operational risks", "optional": False},
            {"agent_type": "reporting_agent", "purpose": "Generate executive compliance report", "optional": False},
        ],
        expected_deliverables=[
            "Executive Compliance Report",
            "Obligations Register",
            "Controls Register",
            "Risk Register",
            "Recommendations",
        ],
        success_criteria=[
            "Policy document found and analyzed",
            "Obligations extracted",
            "Controls identified",
            "Risks assessed",
            "Compliance report generated",
        ],
    ),
    WorkflowType.MEETING_REVIEW: WorkflowDefinition(
        workflow_type=WorkflowType.MEETING_REVIEW,
        name="Meeting Review",
        description=(
            "Analyzes a meeting recording or transcript. Extracts decisions, "
            "action items, risks, and generates meeting minutes."
        ),
        objective_patterns=[
            "review.*meeting", "meeting.*review", "analyze.*meeting",
            "meeting.*analysis", "meeting.*minutes", "minutes.*meeting",
            "review.*recording", "recording.*review", "workshop.*review",
        ],
        agent_plan=[
            {"agent_type": "media_agent", "purpose": "Process audio/video and extract transcript", "optional": True},
            {"agent_type": "meeting_agent", "purpose": "Extract decisions, actions, risks from transcript", "optional": False},
            {"agent_type": "entity_agent", "purpose": "Extract entities, systems, and topics discussed", "optional": False},
            {"agent_type": "workflow_agent", "purpose": "Extract process steps discussed", "optional": True},
            {"agent_type": "reporting_agent", "purpose": "Generate structured meeting minutes", "optional": False},
        ],
        expected_deliverables=[
            "Meeting Minutes",
            "Decision Register",
            "Action Item Register",
            "Risk Log",
            "Entity Map",
        ],
        success_criteria=[
            "Transcript analyzed",
            "Decisions extracted",
            "Actions assigned",
            "Risks identified",
            "Minutes generated",
        ],
    ),
    WorkflowType.FRS_REVIEW: WorkflowDefinition(
        workflow_type=WorkflowType.FRS_REVIEW,
        name="FRS Review",
        description=(
            "Analyzes a Functional Requirements Specification. Extracts "
            "business rules, actors, workflows, and system integrations."
        ),
        objective_patterns=[
            "review.*frs", "frs.*review", "analyze.*frs",
            "frs.*analysis", "functional.*requirement.*review",
            "requirements.*review", "spec.*review",
        ],
        agent_plan=[
            {"agent_type": "retrieval_agent", "purpose": "Find the FRS document and related content", "optional": False},
            {"agent_type": "entity_agent", "purpose": "Extract actors, systems, and entities", "optional": False},
            {"agent_type": "workflow_agent", "purpose": "Extract business processes and workflows", "optional": False},
            {"agent_type": "comparison_agent", "purpose": "Compare against related FRS documents", "optional": True},
            {"agent_type": "reporting_agent", "purpose": "Generate FRS analysis report", "optional": False},
        ],
        expected_deliverables=[
            "FRS Analysis Report",
            "Business Rules Register",
            "Actor Map",
            "Workflow Diagram",
            "Integration Map",
        ],
        success_criteria=[
            "FRS document analyzed",
            "Business rules extracted",
            "Actors identified",
            "Workflows documented",
            "Integrations mapped",
        ],
    ),
    WorkflowType.PROJECT_HEALTH_CHECK: WorkflowDefinition(
        workflow_type=WorkflowType.PROJECT_HEALTH_CHECK,
        name="Project Health Check",
        description=(
            "Evaluates a project's knowledge assets, meetings, documents, "
            "and identifies risks, gaps, and recommendations."
        ),
        objective_patterns=[
            "health.*check", "project.*health", "project.*review",
            "status.*review", "project.*status", "review.*project",
            "project.*assessment",
        ],
        agent_plan=[
            {"agent_type": "asset_agent", "purpose": "Discover all knowledge assets for the project", "optional": False},
            {"agent_type": "graph_agent", "purpose": "Map project dependencies and relationships", "optional": False},
            {"agent_type": "risk_agent", "purpose": "Identify project risks from documents and meetings", "optional": False},
            {"agent_type": "meeting_agent", "purpose": "Analyze recent meetings for decisions and actions", "optional": True},
            {"agent_type": "reporting_agent", "purpose": "Generate health check report", "optional": False},
        ],
        expected_deliverables=[
            "Project Health Report",
            "Risk Register",
            "Asset Inventory",
            "Dependency Map",
            "Recommendations",
        ],
        success_criteria=[
            "All project assets discovered",
            "Risks identified and assessed",
            "Dependencies mapped",
            "Health report generated",
        ],
    ),
    WorkflowType.RISK_ASSESSMENT: WorkflowDefinition(
        workflow_type=WorkflowType.RISK_ASSESSMENT,
        name="Risk Assessment",
        description=(
            "Comprehensive risk assessment across policies, meetings, "
            "projects, and operational documents."
        ),
        objective_patterns=[
            "risk.*assessment", "assess.*risk", "risk.*analysis",
            "analyze.*risk", "risk.*review", "review.*risk",
            "risk.*evaluation", "evaluate.*risk",
        ],
        agent_plan=[
            {"agent_type": "retrieval_agent", "purpose": "Find all risk-related documents", "optional": False},
            {"agent_type": "risk_agent", "purpose": "Identify and assess risks from documents", "optional": False},
            {"agent_type": "policy_agent", "purpose": "Extract controls and compliance obligations", "optional": False},
            {"agent_type": "graph_agent", "purpose": "Map risk dependencies and impacts", "optional": False},
            {"agent_type": "reporting_agent", "purpose": "Generate risk assessment report", "optional": False},
        ],
        expected_deliverables=[
            "Risk Assessment Report",
            "Risk Register",
            "Controls Register",
            "Impact Analysis",
            "Mitigation Recommendations",
        ],
        success_criteria=[
            "All risk sources discovered",
            "Risks identified and scored",
            "Controls mapped",
            "Mitigations recommended",
        ],
    ),
    WorkflowType.COMPLIANCE_REVIEW: WorkflowDefinition(
        workflow_type=WorkflowType.COMPLIANCE_REVIEW,
        name="Compliance Review",
        description=(
            "Reviews documents, policies, and processes for compliance "
            "with regulatory and governance requirements."
        ),
        objective_patterns=[
            "compliance.*review", "review.*compliance", "regulatory.*review",
            "review.*regulatory", "compliance.*check", "audit.*review",
            "governance.*review", "review.*governance",
        ],
        agent_plan=[
            {"agent_type": "retrieval_agent", "purpose": "Find policies, standards, and compliance docs", "optional": False},
            {"agent_type": "policy_agent", "purpose": "Extract obligations, controls, and requirements", "optional": False},
            {"agent_type": "risk_agent", "purpose": "Identify compliance risks and gaps", "optional": False},
            {"agent_type": "comparison_agent", "purpose": "Compare against regulatory requirements", "optional": True},
            {"agent_type": "reporting_agent", "purpose": "Generate compliance report", "optional": False},
        ],
        expected_deliverables=[
            "Compliance Report",
            "Gap Analysis",
            "Obligations Register",
            "Risk Register",
            "Corrective Action Plan",
        ],
        success_criteria=[
            "All compliance documents analyzed",
            "Gaps identified",
            "Obligations documented",
            "Corrective actions recommended",
        ],
    ),
    WorkflowType.KNOWLEDGE_DISCOVERY: WorkflowDefinition(
        workflow_type=WorkflowType.KNOWLEDGE_DISCOVERY,
        name="Knowledge Discovery",
        description=(
            "Explores knowledge assets across spaces, graph, and documents "
            "to build a comprehensive view of a topic, system, or domain."
        ),
        objective_patterns=[
            "discover.*knowledge", "knowledge.*discovery", "explore.*topic",
            "tell me about", "what do we know about", "find.*about",
            "discover.*about", "knowledge.*space.*explore",
        ],
        agent_plan=[
            {"agent_type": "graph_agent", "purpose": "Traverse knowledge graph for entity relationships", "optional": False},
            {"agent_type": "asset_agent", "purpose": "Discover all related knowledge assets", "optional": False},
            {"agent_type": "entity_agent", "purpose": "Extract entities, systems, and relationships", "optional": False},
            {"agent_type": "retrieval_agent", "purpose": "Retrieve relevant document chunks", "optional": False},
            {"agent_type": "reporting_agent", "purpose": "Generate knowledge summary", "optional": False},
        ],
        expected_deliverables=[
            "Knowledge Summary",
            "Entity Map",
            "Asset Inventory",
            "Relationship Diagram",
            "Cross-Space Reference",
        ],
        success_criteria=[
            "Knowledge graph traversed",
            "Assets discovered across spaces",
            "Entities and relationships documented",
            "Comprehensive knowledge summary generated",
        ],
    ),
    WorkflowType.EXECUTIVE_BRIEFING: WorkflowDefinition(
        workflow_type=WorkflowType.EXECUTIVE_BRIEFING,
        name="Executive Briefing",
        description=(
            "Generates a comprehensive executive briefing on a topic, "
            "system, project, or domain. Synthesizes findings from all "
            "knowledge sources into an actionable executive report."
        ),
        objective_patterns=[
            "executive.*brief", "brief.*on", "executive.*summary",
            "executive.*report", "briefing.*on", "status.*brief",
            "update.*on", "overview.*of",
        ],
        agent_plan=[
            {"agent_type": "graph_agent", "purpose": "Map domain knowledge graph", "optional": False},
            {"agent_type": "asset_agent", "purpose": "Discover all relevant assets and spaces", "optional": False},
            {"agent_type": "entity_agent", "purpose": "Extract entities and topics", "optional": False},
            {"agent_type": "summary_agent", "purpose": "Generate executive summaries", "optional": False},
            {"agent_type": "reporting_agent", "purpose": "Generate executive briefing report", "optional": False},
        ],
        expected_deliverables=[
            "Executive Briefing",
            "Key Findings Summary",
            "Decision Support",
            "Risk Overview",
            "Recommended Actions",
        ],
        success_criteria=[
            "Domain knowledge mapped",
            "Key findings extracted",
            "Executive briefing generated",
            "Actionable recommendations provided",
        ],
    ),
}


def _infer_workflow_type(objective: str) -> WorkflowType:
    """Infer the workflow type from a user's objective statement."""
    obj_lower = objective.lower()

    import re as _re
    scored: list[tuple[int, WorkflowType]] = []
    for wf_type, definition in _WORKFLOW_REGISTRY.items():
        for pattern in definition.objective_patterns:
            match = _re.search(pattern, obj_lower)
            if match:
                score = len(match.group())
                scored.append((score, wf_type))
                break

    if scored:
        scored.sort(key=lambda x: -x[0])
        return scored[0][1]

    return WorkflowType.KNOWLEDGE_DISCOVERY


# ── Workflow Execution ────────────────────────────────────────────────────────


class WorkflowExecution:
    """Tracks the state of a single workflow execution (in-memory during run)."""

    def __init__(
        self,
        workflow_type: WorkflowType,
        objective: str,
        session_id: Optional[int] = None,
        project_ids: Optional[list[int]] = None,
        document_id: Optional[str] = None,
    ):
        self.workflow_type = workflow_type
        self.objective = objective
        self.session_id = session_id
        self.project_ids = project_ids or []
        self.document_id = document_id

        self.execution_id: str = f"wf_{int(time.time() * 1000)}_{id(self)}"
        self.status: str = "pending"
        self.steps: list[WorkflowStep] = []
        self.deliverables: dict[str, Any] = {}
        self.merged_entities: list[str] = []
        self.merged_actions: list[dict[str, Any]] = []
        self.merged_decisions: list[dict[str, Any]] = []
        self.merged_risks: list[dict[str, Any]] = []
        self.merged_workflows: list[dict[str, Any]] = []
        self.execution_summary: str = ""
        self.error: Optional[str] = None
        self.started_at: Optional[str] = None
        self.completed_at: Optional[str] = None
        self.total_duration_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "workflow_type": self.workflow_type.value if isinstance(self.workflow_type, WorkflowType) else self.workflow_type,
            "objective": self.objective,
            "status": self.status,
            "steps": [s.to_dict() for s in self.steps],
            "deliverables": self.deliverables,
            "merged_entities": self.merged_entities,
            "merged_actions_count": len(self.merged_actions),
            "merged_decisions_count": len(self.merged_decisions),
            "merged_risks_count": len(self.merged_risks),
            "execution_summary": self.execution_summary,
            "error": self.error,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "total_duration_ms": round(self.total_duration_ms, 1),
        }


# ── Workflow Engine ───────────────────────────────────────────────────────────


class WorkflowEngine:
    """Autonomous workflow engine with DB persistence.

    Orchestrates multi-agent execution for enterprise knowledge tasks.
    Every execution is persisted to workflow_execution_records so it
    survives restarts and is visible across workers.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Public API ─────────────────────────────────────────────────────────

    async def resolve_and_execute(
        self,
        objective: str,
        session_id: Optional[int] = None,
        project_ids: Optional[list[int]] = None,
        document_id: Optional[str] = None,
        force_type: Optional[str] = None,
    ) -> WorkflowExecution:
        """Resolve an objective into a workflow type and execute it.

        1. Resolves the objective to a WorkflowType
        2. Creates a WorkflowExecution
        3. Executes the workflow plan
        4. Generates LLM-driven deliverables
        5. Persists everything to the database
        6. Returns the completed execution
        """
        # 1. Resolve workflow type
        if force_type and force_type in [t.value for t in WorkflowType]:
            wf_type = WorkflowType(force_type)
        else:
            wf_type = _infer_workflow_type(objective)

        logger.info(
            "[WORKFLOW] Resolved objective=%r → workflow_type=%s",
            objective[:80], wf_type.value,
        )

        # 2. Create execution
        execution = WorkflowExecution(
            workflow_type=wf_type,
            objective=objective,
            session_id=session_id,
            project_ids=project_ids,
            document_id=document_id,
        )

        # 3. Execute
        try:
            await self._execute(execution)
        finally:
            # 4. Persist to DB (always — even on failure, so failed workflows survive restart)
            await self._persist_execution(execution)

        return execution

    async def _execute(self, execution: WorkflowExecution) -> None:
        """Execute a workflow plan."""
        start_time = time.time()
        execution.status = "running"
        execution.started_at = datetime.utcnow().isoformat()

        try:
            definition = _WORKFLOW_REGISTRY.get(execution.workflow_type)
            if not definition:
                execution.status = "failed"
                execution.error = f"Unknown workflow type: {execution.workflow_type}"
                execution.completed_at = datetime.utcnow().isoformat()
                return

            logger.info(
                "[WORKFLOW] Executing %s: %d agents, %d deliverables",
                definition.name, len(definition.agent_plan),
                len(definition.expected_deliverables),
            )

            # Create step objects
            for i, agent_step in enumerate(definition.agent_plan):
                step = WorkflowStep(
                    step_id=i + 1,
                    agent_type=agent_step["agent_type"],
                    purpose=agent_step["purpose"],
                    status="pending",
                )
                execution.steps.append(step)

            # Execute each agent step
            bundle = await self._execute_agent_steps(execution, definition)

            # Generate LLM-driven deliverables
            await self._generate_deliverables(execution, definition, bundle)

            # Store results in agent memory
            await self._store_workflow_results(execution)

            execution.status = "completed"
            execution.total_duration_ms = (time.time() - start_time) * 1000
            execution.completed_at = datetime.utcnow().isoformat()
            execution.execution_summary = self._build_summary(execution, definition)

            logger.info(
                "[WORKFLOW] Completed %s in %.0fms: %d steps, %d deliverables",
                definition.name, execution.total_duration_ms,
                len(execution.steps), len(execution.deliverables),
            )

        except Exception as exc:
            execution.status = "failed"
            execution.error = str(exc)
            execution.completed_at = datetime.utcnow().isoformat()
            execution.total_duration_ms = (time.time() - start_time) * 1000
            logger.error("[WORKFLOW] Execution failed: %s", exc)

    async def _execute_agent_steps(
        self,
        execution: WorkflowExecution,
        definition: WorkflowDefinition,
    ) -> dict[str, Any]:
        """Execute each agent step in the workflow plan."""
        from app.services.agent_runtime_service import AgentCoordinator

        coordinator = AgentCoordinator(self.db)
        await coordinator.initialize()

        merged_bundle: dict[str, Any] = {
            "entities": [],
            "actions": [],
            "decisions": [],
            "risks": [],
            "workflows": [],
            "summaries": [],
        }

        for step in execution.steps:
            step.status = "running"
            step_start = time.time()

            try:
                agent_bundle = await coordinator.execute_agent_plan(
                    intent=self._agent_type_to_intent(step.agent_type),
                    user_query=execution.objective,
                    session_id=execution.session_id,
                    document_id=execution.document_id,
                    project_ids=execution.project_ids if execution.project_ids else None,
                )

                step.duration_ms = (time.time() - step_start) * 1000
                step.status = "completed"

                merged_bundle["entities"].extend(agent_bundle.merged_entities)
                merged_bundle["actions"].extend(agent_bundle.merged_actions)
                merged_bundle["decisions"].extend(agent_bundle.merged_decisions)
                merged_bundle["risks"].extend(agent_bundle.merged_risks)
                merged_bundle["workflows"].extend(agent_bundle.merged_workflows)
                if agent_bundle.merged_summaries:
                    merged_bundle["summaries"].extend(agent_bundle.merged_summaries)

                step.result = {
                    "agents_executed": len(agent_bundle.agent_results),
                    "findings_count": len(agent_bundle.agent_results),
                    "execution_summary": agent_bundle.execution_summary[:500],
                }

                logger.info(
                    "[WORKFLOW] Step %d/%d (%s): completed in %.0fms",
                    step.step_id, len(execution.steps),
                    step.agent_type, step.duration_ms,
                )

            except Exception as exc:
                step.duration_ms = (time.time() - step_start) * 1000
                step.status = "failed"
                step.error = str(exc)
                logger.warning(
                    "[WORKFLOW] Step %d/%d (%s): failed: %s",
                    step.step_id, len(execution.steps),
                    step.agent_type, exc,
                )

        # Deduplicate merged data
        execution.merged_entities = list(set(
            e for e in merged_bundle["entities"] if e
        ))
        execution.merged_actions = [
            a for a in merged_bundle["actions"] if isinstance(a, dict) and a.get("action")
        ][:50]
        execution.merged_decisions = [
            d for d in merged_bundle["decisions"] if isinstance(d, dict) and d.get("decision")
        ][:30]
        execution.merged_risks = [
            r for r in merged_bundle["risks"] if isinstance(r, dict) and r.get("risk")
        ][:30]
        execution.merged_workflows = merged_bundle["workflows"][:10]

        return merged_bundle

    # ── LLM-Driven Deliverable Generation ──────────────────────────────────

    async def _generate_deliverables(
        self,
        execution: WorkflowExecution,
        definition: WorkflowDefinition,
        bundle: dict[str, Any],
    ) -> None:
        """Generate structured deliverables from agent findings.

        Uses the provider gateway to produce LLM-driven report content
        when possible, falling back to template-based content.
        """
        deliverables: dict[str, Any] = {}

        # 1. Executive Report / Summary
        summary_text = self._build_executive_summary(execution, definition)
        if summary_text:
            deliverables["executive_summary"] = summary_text

        # 2. Entity Map
        if execution.merged_entities:
            deliverables["entities"] = execution.merged_entities[:30]

        # 3. Action Register
        if execution.merged_actions:
            deliverables["actions"] = execution.merged_actions[:20]

        # 4. Decision Register
        if execution.merged_decisions:
            deliverables["decisions"] = execution.merged_decisions[:20]

        # 5. Risk Register
        if execution.merged_risks:
            deliverables["risks"] = execution.merged_risks[:20]

        # 6. Workflow findings
        if execution.merged_workflows:
            deliverables["workflows"] = execution.merged_workflows[:5]

        # 7. Deliverable-specific content via LLM
        for deliverable in definition.expected_deliverables:
            dl_key = deliverable.lower().replace(" ", "_").replace("'", "")
            if dl_key not in deliverables:
                llm_content = await self._generate_deliverable_with_llm(
                    deliverable, execution, definition
                )
                deliverables[dl_key] = llm_content

        execution.deliverables = deliverables

    async def _generate_deliverable_with_llm(
        self,
        deliverable_name: str,
        execution: WorkflowExecution,
        definition: WorkflowDefinition,
    ) -> str:
        """Use the provider gateway to generate LLM-driven deliverable content.

        Falls back to template-based generation if no provider is available.
        """
        try:
            from app.services import provider_gateway_service

            prompt = self._build_deliverable_prompt(deliverable_name, execution, definition)

            # Resolve a model_id for generation via TaskMapping
            model_id = ""
            try:
                from sqlalchemy import select as sa_sel
                from app.db.config_models import TaskMapping

                result = await self.db.execute(
                    sa_sel(TaskMapping).where(TaskMapping.task_type == "chat")
                )
                tm = result.scalar_one_or_none()
                if tm and tm.model_id:
                    model_id = tm.model_id
            except Exception:
                pass

            response_text, _ = await provider_gateway_service.generate(
                db=self.db,
                prompt=prompt,
                model_id=model_id,
                system=(
                    "You are an enterprise report writer for DocTel\'s Knowledge Base AI. "
                    "Generate a structured, professional report section based on the findings "
                    "provided. Use clear headings, bullet points, and business-appropriate language. "
                    "Do not fabricate information — only use the findings provided."
                ),
            )

            content = (response_text or "").strip()
            if content:
                logger.info(
                    "[WORKFLOW_LLM] Generated deliverable '%s' via LLM (%d chars)",
                    deliverable_name, len(content),
                )
                return content

        except Exception as exc:
            logger.warning(
                "[WORKFLOW_LLM] LLM generation failed for '%s': %s. Using template.",
                deliverable_name, exc,
            )

        # Fallback to template
        return self._generate_deliverable_template(deliverable_name, execution, definition)

    def _build_deliverable_prompt(
        self,
        deliverable_name: str,
        execution: WorkflowExecution,
        definition: WorkflowDefinition,
    ) -> str:
        """Build an LLM prompt for generating a specific deliverable section."""
        parts = [
            f"Generate the following deliverable for a {definition.name}:",
            f"**Deliverable:** {deliverable_name}",
            f"**Objective:** {execution.objective}",
            "",
            "**Findings from analysis:**",
        ]

        if execution.merged_entities:
            parts.append(f"- Entities: {', '.join(execution.merged_entities[:15])}")

        if execution.merged_actions:
            parts.append("- Action Items:")
            for a in execution.merged_actions[:8]:
                parts.append(f"  - {a.get('action', '')} (Owner: {a.get('owner', 'N/A')})")

        if execution.merged_decisions:
            parts.append("- Decisions:")
            for d in execution.merged_decisions[:5]:
                parts.append(f"  - {d.get('decision', '')}")

        if execution.merged_risks:
            parts.append("- Risks:")
            for r in execution.merged_risks[:5]:
                parts.append(f"  - {r.get('risk', '')} (Severity: {r.get('severity', 'N/A')})")

        if execution.merged_workflows:
            parts.append(f"- Workflows identified: {len(execution.merged_workflows)}")

        parts.append("")
        parts.append("Generate the deliverable content as a structured report section with headings and bullet points.")

        return "\n".join(parts)

    def _build_executive_summary(
        self,
        execution: WorkflowExecution,
        definition: WorkflowDefinition,
    ) -> str:
        """Build a structured executive summary from workflow results."""
        parts = [
            f"# {definition.name}: {execution.objective}",
            "",
            f"**Workflow Type:** {definition.workflow_type.value}",
            f"**Agents Executed:** {len(execution.steps)}",
            f"**Entities Discovered:** {len(execution.merged_entities)}",
            f"**Actions Extracted:** {len(execution.merged_actions)}",
            f"**Decisions:** {len(execution.merged_decisions)}",
            f"**Risks Identified:** {len(execution.merged_risks)}",
        ]

        completed = sum(1 for s in execution.steps if s.status == "completed")
        failed = sum(1 for s in execution.steps if s.status == "failed")
        parts.append(f"**Steps Completed:** {completed}/{len(execution.steps)}")
        if failed:
            parts.append(f"**Steps Failed:** {failed}")

        if execution.merged_entities:
            parts.append(f"\n**Key Entities:** {', '.join(execution.merged_entities[:15])}")

        if execution.merged_actions:
            parts.append(f"\n**Top Actions:**")
            for a in execution.merged_actions[:5]:
                owner = a.get("owner", "N/A")
                parts.append(f"- {a.get('action', '')} [{owner}]")

        if execution.merged_risks:
            parts.append(f"\n**Top Risks:**")
            for r in execution.merged_risks[:5]:
                severity = r.get("severity", "N/A")
                parts.append(f"- {r.get('risk', '')} [Severity: {severity}]")

        parts.append(f"\n**Deliverables:**")
        for d in definition.expected_deliverables:
            parts.append(f"- {d}")

        return "\n".join(parts)

    def _generate_deliverable_template(
        self,
        deliverable_name: str,
        execution: WorkflowExecution,
        definition: WorkflowDefinition,
    ) -> str:
        """Template-based deliverable content (fallback when LLM is unavailable)."""
        name_lower = deliverable_name.lower()

        if "obligation" in name_lower or "control" in name_lower:
            lines = [f"# {deliverable_name}", ""]
            if execution.merged_actions:
                for a in execution.merged_actions[:10]:
                    lines.append(f"- {a.get('action', '')} [Obligation]")
            else:
                lines.append("No specific obligations extracted.")
            return "\n".join(lines)

        if "risk" in name_lower:
            lines = [f"# {deliverable_name}", ""]
            if execution.merged_risks:
                for r in execution.merged_risks[:10]:
                    sev = r.get("severity", "N/A")
                    lines.append(f"- {r.get('risk', '')} (Severity: {sev})")
            else:
                lines.append("No risks identified.")
            return "\n".join(lines)

        if "action" in name_lower:
            lines = [f"# {deliverable_name}", ""]
            if execution.merged_actions:
                for a in execution.merged_actions[:10]:
                    owner = a.get("owner", "N/A")
                    priority = a.get("priority", "N/A")
                    lines.append(f"- {a.get('action', '')} [Owner: {owner}, Priority: {priority}]")
            else:
                lines.append("No actions extracted.")
            return "\n".join(lines)

        if "decision" in name_lower:
            lines = [f"# {deliverable_name}", ""]
            if execution.merged_decisions:
                for d in execution.merged_decisions[:10]:
                    by = d.get("made_by", "N/A")
                    lines.append(f"- {d.get('decision', '')} [By: {by}]")
            else:
                lines.append("No decisions recorded.")
            return "\n".join(lines)

        if "entity" in name_lower or "actor" in name_lower:
            lines = [f"# {deliverable_name}", ""]
            if execution.merged_entities:
                lines.extend(f"- {e}" for e in execution.merged_entities[:30])
            else:
                lines.append("No entities extracted.")
            return "\n".join(lines)

        if "workflow" in name_lower or "process" in name_lower:
            lines = [f"# {deliverable_name}", ""]
            if execution.merged_workflows:
                for wf in execution.merged_workflows[:5]:
                    steps = wf.get("steps", [])
                    if steps:
                        lines.append(f"- {len(steps)} workflow steps identified")
                    else:
                        lines.append(f"- Workflow: {wf.get('name', 'Unnamed')}")
            else:
                lines.append("No workflows extracted.")
            return "\n".join(lines)

        if "recommendation" in name_lower or "corrective" in name_lower:
            lines = [f"# {deliverable_name}", ""]
            lines.append("Based on the analysis, the following recommendations are proposed:")
            if execution.merged_risks:
                lines.append("1. Address identified risks according to severity")
            if execution.merged_actions:
                lines.append("2. Track and close outstanding action items")
            if execution.merged_decisions:
                lines.append("3. Validate and implement recorded decisions")
            lines.append("4. Conduct follow-up review after implementing changes")
            return "\n".join(lines)

        if "gap" in name_lower:
            lines = [f"# {deliverable_name}", ""]
            lines.append("Gap analysis was performed across available knowledge assets.")
            lines.append("Review the full findings for specific gaps identified.")
            return "\n".join(lines)

        return f"# {deliverable_name}\n\n*Generated from workflow analysis.*"

    # ── Memory & DB Persistence ────────────────────────────────────────────

    async def _persist_execution(self, execution: WorkflowExecution) -> None:
        """Persist the workflow execution to the database."""
        try:
            from app.db.enterprise_models import WorkflowExecutionRecord

            # Check if already persisted
            result = await self.db.execute(
                select(WorkflowExecutionRecord).where(
                    WorkflowExecutionRecord.execution_id == execution.execution_id
                )
            )
            existing = result.scalar_one_or_none()
            if existing:
                logger.debug(
                    "[WORKFLOW_PERSIST] Execution %s already persisted, updating",
                    execution.execution_id,
                )
                existing.status = execution.status
                existing.steps_json = json.dumps([s.to_dict() for s in execution.steps])
                existing.deliverables_json = json.dumps(execution.deliverables)
                existing.merged_entities_json = json.dumps(execution.merged_entities)
                existing.merged_actions_json = json.dumps(execution.merged_actions)
                existing.merged_decisions_json = json.dumps(execution.merged_decisions)
                existing.merged_risks_json = json.dumps(execution.merged_risks)
                existing.merged_workflows_json = json.dumps(execution.merged_workflows)
                existing.execution_summary = execution.execution_summary
                existing.error_message = execution.error or ""
                existing.total_duration_ms = execution.total_duration_ms
                existing.completed_at = (
                    datetime.fromisoformat(execution.completed_at.replace("Z", "+00:00"))
                    if execution.completed_at else None
                )
            else:
                record = WorkflowExecutionRecord(
                    execution_id=execution.execution_id,
                    workflow_type=execution.workflow_type.value,
                    objective=execution.objective,
                    status=execution.status,
                    session_id=execution.session_id,
                    document_id=execution.document_id,
                    project_ids_json=json.dumps(execution.project_ids),
                    steps_json=json.dumps([s.to_dict() for s in execution.steps]),
                    deliverables_json=json.dumps(execution.deliverables),
                    merged_entities_json=json.dumps(execution.merged_entities),
                    merged_actions_json=json.dumps(execution.merged_actions),
                    merged_decisions_json=json.dumps(execution.merged_decisions),
                    merged_risks_json=json.dumps(execution.merged_risks),
                    merged_workflows_json=json.dumps(execution.merged_workflows),
                    execution_summary=execution.execution_summary,
                    error_message=execution.error or "",
                    total_duration_ms=execution.total_duration_ms,
                    started_at=(
                        datetime.fromisoformat(execution.started_at.replace("Z", "+00:00"))
                        if execution.started_at else None
                    ),
                    completed_at=(
                        datetime.fromisoformat(execution.completed_at.replace("Z", "+00:00"))
                        if execution.completed_at else None
                    ),
                )
                self.db.add(record)

            await self.db.commit()
            logger.info(
                "[WORKFLOW_PERSIST] Persisted execution %s (%s)",
                execution.execution_id, execution.status,
            )

        except Exception as exc:
            await self.db.rollback()
            logger.warning("[WORKFLOW_PERSIST] Failed to persist execution: %s", exc)

    async def _store_workflow_results(self, execution: WorkflowExecution) -> None:
        """Store workflow results in agent memory."""
        try:
            from app.services.agent_memory_service import AgentMemoryService, MemoryType

            mem = AgentMemoryService(self.db)

            if execution.session_id is not None:
                if execution.execution_summary:
                    await mem.store_memory(
                        agent_execution_id=-1,
                        key=f"workflow_{execution.workflow_type.value}_summary",
                        value={"summary": execution.execution_summary},
                        memory_type=MemoryType.EPISODIC.value,
                        session_id=execution.session_id,
                    )

                if execution.merged_entities:
                    await mem.store_memory(
                        agent_execution_id=-1,
                        key=f"workflow_{execution.workflow_type.value}_entities",
                        value={"entities": execution.merged_entities},
                        memory_type=MemoryType.SEMANTIC.value,
                        session_id=execution.session_id,
                    )

                await mem.store_memory(
                    agent_execution_id=-1,
                    key=f"workflow_{execution.workflow_type.value}_findings",
                    value={
                        "actions": execution.merged_actions[:10],
                        "decisions": execution.merged_decisions[:10],
                        "risks": execution.merged_risks[:10],
                    },
                    memory_type=MemoryType.EPISODIC.value,
                    session_id=execution.session_id,
                )

                logger.info(
                    "[WORKFLOW_MEMORY] Stored workflow results for session %d",
                    execution.session_id,
                )

        except Exception as exc:
            logger.warning("[WORKFLOW_MEMORY] Failed to store results: %s", exc)

    def _build_summary(
        self,
        execution: WorkflowExecution,
        definition: WorkflowDefinition,
    ) -> str:
        """Build a human-readable execution summary."""
        completed = sum(1 for s in execution.steps if s.status == "completed")
        failed = sum(1 for s in execution.steps if s.status == "failed")

        parts = [
            f"# {definition.name} Complete",
            "",
            f"**Objective:** {execution.objective}",
            f"**Status:** {completed}/{len(execution.steps)} steps completed",
            f"**Duration:** {execution.total_duration_ms:.0f}ms",
        ]

        if failed:
            parts.append(f"**Failed steps:** {failed}")

        parts.append("\n## Execution Steps")
        for step in execution.steps:
            icon = "\u2705" if step.status == "completed" else "\u274c" if step.status == "failed" else "\u23f3"
            parts.append(f"{icon} **Step {step.step_id}:** {step.purpose} ({step.status})")

        if execution.merged_entities:
            parts.append(f"\n## Entities Discovered ({len(execution.merged_entities)})")
            parts.append(", ".join(execution.merged_entities[:20]))

        if execution.merged_actions:
            parts.append(f"\n## Actions Extracted ({len(execution.merged_actions)})")

        if execution.merged_decisions:
            parts.append(f"\n## Decisions ({len(execution.merged_decisions)})")

        if execution.merged_risks:
            parts.append(f"\n## Risks Identified ({len(execution.merged_risks)})")

        parts.append(f"\n## Deliverables Generated ({len(execution.deliverables)})")
        for key in execution.deliverables:
            parts.append(f"- {key.replace('_', ' ').title()}")

        return "\n".join(parts)

    # ── Helpers ───────────────────────────────────────────────────────────

    def _agent_type_to_intent(self, agent_type: str) -> str:
        """Map an agent type to a knowledge intent for the coordinator."""
        mapping = {
            "retrieval_agent": "question_answering",
            "graph_agent": "knowledge_discovery",
            "asset_agent": "knowledge_discovery",
            "media_agent": "audio_analysis",
            "workflow_agent": "workflow_extraction",
            "meeting_agent": "meeting_analysis",
            "risk_agent": "risk_assessment",
            "reporting_agent": "report_generation",
            "policy_agent": "policy_review",
            "comparison_agent": "comparison",
            "entity_agent": "knowledge_discovery",
            "summary_agent": "executive_summary",
        }
        return mapping.get(agent_type, "question_answering")

    # ── DB-Backed Workflow Management ──────────────────────────────────────

    async def get_execution(self, execution_id: str) -> Optional[dict[str, Any]]:
        """Get a workflow execution from the database by ID."""
        try:
            from app.db.enterprise_models import WorkflowExecutionRecord

            result = await self.db.execute(
                select(WorkflowExecutionRecord).where(
                    WorkflowExecutionRecord.execution_id == execution_id
                )
            )
            record = result.scalar_one_or_none()
            return record.to_dict() if record else None
        except Exception as exc:
            logger.warning("[WORKFLOW_DB] get_execution failed: %s", exc)
            return None

    async def list_executions(
        self,
        limit: int = 20,
        status_filter: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """List workflow executions from the database."""
        try:
            from app.db.enterprise_models import WorkflowExecutionRecord

            query = select(WorkflowExecutionRecord)
            if status_filter:
                query = query.where(WorkflowExecutionRecord.status == status_filter)
            query = query.order_by(desc(WorkflowExecutionRecord.created_at)).limit(limit)

            result = await self.db.execute(query)
            records = result.scalars().all()
            return [r.to_dict() for r in records]
        except Exception as exc:
            logger.warning("[WORKFLOW_DB] list_executions failed: %s", exc)
            return []

    async def list_executions_by_session(
        self,
        session_id: int,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """List workflow executions for a session."""
        try:
            from app.db.enterprise_models import WorkflowExecutionRecord

            query = (
                select(WorkflowExecutionRecord)
                .where(WorkflowExecutionRecord.session_id == session_id)
                .order_by(desc(WorkflowExecutionRecord.created_at))
                .limit(limit)
            )
            result = await self.db.execute(query)
            records = result.scalars().all()
            return [r.to_dict() for r in records]
        except Exception as exc:
            logger.warning("[WORKFLOW_DB] list_executions_by_session failed: %s", exc)
            return []

    def get_available_workflows(self) -> list[dict[str, Any]]:
        """List all available workflow definitions."""
        result = []
        for wf_type, definition in _WORKFLOW_REGISTRY.items():
            result.append({
                "workflow_type": wf_type.value,
                "name": definition.name,
                "description": definition.description,
                "agent_count": len(definition.agent_plan),
                "expected_deliverables": definition.expected_deliverables,
                "success_criteria": definition.success_criteria,
            })
        return result


# ── Convenience Wrapper ───────────────────────────────────────────────────────


async def execute_workflow(
    db: AsyncSession,
    objective: str,
    session_id: Optional[int] = None,
    project_ids: Optional[list[int]] = None,
    document_id: Optional[str] = None,
    force_type: Optional[str] = None,
) -> dict[str, Any]:
    """Convenience function to create a workflow engine and execute.

    Usage:
        result = await execute_workflow(
            db=db,
            objective="Review CRM Policy",
            session_id=123,
        )
        print(result["execution_summary"])
    """
    engine = WorkflowEngine(db)
    execution = await engine.resolve_and_execute(
        objective=objective,
        session_id=session_id,
        project_ids=project_ids,
        document_id=document_id,
        force_type=force_type,
    )
    return execution.to_dict()
