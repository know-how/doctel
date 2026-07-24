"""
tool_execution_service.py — DocTel Tool Execution Layer

Executes the tools defined in an ExecutionPlan.
Collects evidence into an EvidenceBundle for the response strategy.

Architecture:

Execution Plan
  ↓
Tool Executor (this service)
  ├─ RAG_SEARCH → retrieves chunks → adds to evidence
  ├─ POLICY_ANALYSIS → analyzes content → extracts obligations/controls/risks
  ├─ DECISION_EXTRACTION → extracts decisions from content
  ├─ ACTION_EXTRACTION → extracts action items from content
  ├─ WORKFLOW_EXTRACTION → extracts workflow steps
  ├─ MEETING_ANALYSIS → generates structured meeting report
  ├─ DOCUMENT_COMPARE → compares two documents
  ├─ DOCUMENT_SUMMARY → generates executive summary
  ├─ RISK_ANALYSIS → identifies risks
  ├─ FRS_ANALYSIS → analyzes functional requirements
  ├─ AUDIO_ANALYSIS → uses session transcript
  ├─ ENTITY_EXTRACTION → extracts entities and topics
  └─ CHAT → generates final answer from evidence
  ↓
EvidenceBundle
  ↓
Response Strategy
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Optional

from app.services.tool_planner_service import (
    ExecutionPlan,
    ExecutionObserver,
    ToolType,
    _apply_context_adjustments,
)

logger = logging.getLogger(__name__)


# ── Tool Result ──────────────────────────────────────────────────────────

class ToolResult:
    """Result of a single tool execution."""

    def __init__(
        self,
        tool_name: str,
        success: bool,
        result: Any = None,
        execution_ms: float = 0.0,
        metadata: Optional[dict[str, Any]] = None,
        error: Optional[str] = None,
    ):
        self.tool_name = tool_name
        self.success = success
        self.result = result
        self.execution_ms = execution_ms
        self.metadata = metadata or {}
        self.error = error

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "success": self.success,
            "result": self.result,
            "execution_ms": round(self.execution_ms, 1),
            "metadata": self.metadata,
            "error": self.error,
        }


# ── Evidence Bundle ──────────────────────────────────────────────────────

class EvidenceBundle:
    """
    Combined evidence from all executed tools.

    This is the input to the Response Strategy and ultimately the LLM.
    Fields are populated by different tools during execution.
    """

    def __init__(self):
        self.results: list[ToolResult] = []
        self.sources: list[dict[str, Any]] = []      # From RAG_SEARCH
        self.entities: list[str] = []                  # From ENTITY_EXTRACTION
        self.risks: list[dict[str, Any]] = []          # From RISK_ANALYSIS
        self.actions: list[dict[str, Any]] = []        # From ACTION_EXTRACTION
        self.decisions: list[dict[str, Any]] = []      # From DECISION_EXTRACTION
        self.workflows: list[dict[str, Any]] = []      # From WORKFLOW_EXTRACTION
        self.summary: Optional[str] = None              # From DOCUMENT_SUMMARY / MEETING_ANALYSIS
        self.comparison: Optional[dict[str, Any]] = None  # From DOCUMENT_COMPARE
        self.policy_analysis: Optional[dict[str, Any]] = None  # From POLICY_ANALYSIS
        self.meeting_report: Optional[dict[str, Any]] = None   # From MEETING_ANALYSIS
        self.audio_analysis: Optional[dict[str, Any]] = None   # From AUDIO_ANALYSIS
        self.rag_context: Optional[str] = None           # Raw RAG context string

    def add_result(self, result: ToolResult) -> None:
        """Record a tool result."""
        self.results.append(result)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sources_count": len(self.sources),
            "entities_count": len(self.entities),
            "risks": len(self.risks),
            "actions": len(self.actions),
            "decisions": len(self.decisions),
            "workflows": len(self.workflows),
            "has_summary": self.summary is not None,
            "has_comparison": self.comparison is not None,
            "has_policy_analysis": self.policy_analysis is not None,
            "has_meeting_report": self.meeting_report is not None,
            "tools_executed": len(self.results),
            "tool_results": [r.to_dict() for r in self.results],
        }

    def build_context_string(self) -> str:
        """Build a consolidated context string from all evidence for the LLM."""
        parts = []

        if self.summary:
            parts.append(f"[DOCUMENT SUMMARY]\n{self.summary}\n")

        if self.sources:
            sources_str = "\n\n".join(
                f"Source: {s.get('filename', 'Unknown')} (Section {s.get('chunk_index', 0)})\n"
                f"Content: {(s.get('text', '') or '')[:1500]}"
                for s in self.sources[:10]
            )
            parts.append(f"[RETRIEVED SOURCES]\n{sources_str}\n")

        if self.rag_context:
            parts.append(f"[RAG CONTEXT]\n{self.rag_context}\n")

        if self.risks:
            risks_str = "\n".join(
                f"- {r.get('risk', '')} [Likelihood: {r.get('likelihood', 'N/A')}, "
                f"Impact: {r.get('impact', 'N/A')}, Severity: {r.get('severity', 'N/A')}]"
                for r in self.risks
            )
            parts.append(f"[IDENTIFIED RISKS]\n{risks_str}\n")

        if self.actions:
            actions_str = "\n".join(
                f"- {a.get('action', '')} [Owner: {a.get('owner', 'N/A')}, "
                f"Due: {a.get('due_date', 'N/A')}, Priority: {a.get('priority', 'N/A')}]"
                for a in self.actions
            )
            parts.append(f"[ACTION ITEMS]\n{actions_str}\n")

        if self.decisions:
            decisions_str = "\n".join(
                f"- {d.get('decision', '')} [By: {d.get('made_by', 'N/A')}, "
                f"Rationale: {d.get('rationale', 'N/A')}]"
                for d in self.decisions
            )
            parts.append(f"[DECISIONS]\n{decisions_str}\n")

        if self.comparison:
            parts.append(
                f"[COMPARISON]\n"
                f"Similarities: {json.dumps(self.comparison.get('similarities', []))}\n"
                f"Differences: {json.dumps(self.comparison.get('differences', []))}\n"
                f"Gaps: {json.dumps(self.comparison.get('gaps', []))}\n"
            )

        if self.policy_analysis:
            pa = self.policy_analysis
            parts.append(
                f"[POLICY ANALYSIS]\n"
                f"Obligations: {json.dumps(pa.get('obligations', []))}\n"
                f"Controls: {json.dumps(pa.get('controls', []))}\n"
            )

        return "\n\n".join(parts)


# ── LLM Helper ───────────────────────────────────────────────────────────
# Uses a simple prompt-response pattern for LLM-based tools.

async def _call_llm(
    system_prompt: str,
    user_prompt: str,
    db: Any = None,
    model: str = "default",
) -> Optional[str]:
    """Call an LLM with a system prompt and user prompt.

    Uses the provider gateway for model routing via the provided DB session.
    Falls back gracefully on failure.
    """
    import asyncio
    try:
        from app.services.provider_gateway_service import generate as gateway_generate

        if db is None:
            # Fallback: create a short-lived session
            from app.db.database import async_session_local
            async with async_session_local() as session:
                answer, _ = await asyncio.wait_for(
                    gateway_generate(session, user_prompt, model_id=model, system=system_prompt),
                    timeout=60.0,
                )
                return answer
        else:
            answer, _ = await asyncio.wait_for(
                gateway_generate(db, user_prompt, model_id=model, system=system_prompt),
                timeout=60.0,
            )
            return answer
    except asyncio.TimeoutError:
        logger.warning("[TOOL_EXEC] LLM call timed out after 60s")
        return None
    except Exception as e:
        logger.warning("[TOOL_EXEC] LLM call failed: %s", e)
        return None


# ── Tool Implementations ─────────────────────────────────────────────────

async def _execute_rag_search(
    user_query: str,
    project_ids: list[int],
    db: Any,
    observer: ExecutionObserver,
    document_id: Optional[str] = None,
) -> ToolResult:
    """Execute RAG_SEARCH: retrieve relevant chunks from vector store."""
    observer.start_tool("rag_search")
    start = time.time()

    try:
        from app.services.rag_service import get_rag_answer_scoped

        rag_result = await get_rag_answer_scoped(
            project_ids=project_ids,
            user_query=user_query,
            db=db,
            document_id=document_id,
        )

        citations = rag_result.get("citations", [])
        context = "\n\n".join(
            f"Source: {c.get('filename', 'Unknown')}, Chunk {c.get('chunk_index', 0)}\n"
            f"Content: {(c.get('text', '') or '')[:1500]}"
            for c in citations
        ) if citations else None

        elapsed_ms = (time.time() - start) * 1000
        observer.finish_tool("rag_search", {
            "citation_count": len(citations),
            "context_length": len(context or ""),
        })

        return ToolResult(
            tool_name="rag_search",
            success=True,
            result={
                "citations": citations,
                "context": context,
                "answer_text": rag_result.get("answer_text", ""),
            },
            execution_ms=elapsed_ms,
            metadata={"citation_count": len(citations)},
        )
    except Exception as e:
        elapsed_ms = (time.time() - start) * 1000
        observer.fail_tool("rag_search", str(e))
        return ToolResult(
            tool_name="rag_search",
            success=False,
            result=None,
            execution_ms=elapsed_ms,
            error=str(e),
        )


async def _execute_llm_analysis_tool(
    tool_name: str,
    content: str,
    system_prompt: str,
    user_prompt_template: str,
    observer: ExecutionObserver,
) -> ToolResult:
    """Generic executor for LLM-based analysis tools (policy, risk, action, etc.)."""
    observer.start_tool(tool_name)
    start = time.time()

    try:
        user_prompt = user_prompt_template.format(content=content[:8000])
        response = await _call_llm(system_prompt, user_prompt)

        # Try to parse JSON from response
        structured = None
        if response:
            import re
            json_match = re.search(r"```json\n(.*?)\n```", response, re.DOTALL)
            if json_match:
                structured = json.loads(json_match.group(1))

        elapsed_ms = (time.time() - start) * 1000
        observer.finish_tool(tool_name, {
            "response_length": len(response or ""),
            "has_structured": structured is not None,
        })

        return ToolResult(
            tool_name=tool_name,
            success=True,
            result=structured or {"raw_response": response},
            execution_ms=elapsed_ms,
        )
    except Exception as e:
        elapsed_ms = (time.time() - start) * 1000
        observer.fail_tool(tool_name, str(e))
        return ToolResult(
            tool_name=tool_name,
            success=False,
            result=None,
            execution_ms=elapsed_ms,
            error=str(e),
        )


async def _execute_policy_analysis(content: str, observer: ExecutionObserver) -> ToolResult:
    """Extract policy obligations, controls, and risks from content."""
    system = (
        "You are a policy compliance analyst. Extract structured information from policy content. "
        "Return a JSON object with: obligations (list), controls (list), risks (list). "
        "Wrap the JSON in ```json ... ``` tags."
    )
    template = (
        "Analyze the following policy content and extract:\n"
        "1. OBLIGATIONS: What must be done (required actions)\n"
        "2. CONTROLS: What controls or safeguards are specified\n"
        "3. RISKS: What risks are identified or implied\n\n"
        "Content:\n{content}\n\n"
        "Return as JSON wrapped in ```json ... ``` tags."
    )
    return await _execute_llm_analysis_tool("policy_analysis", content, system, template, observer)


async def _execute_frs_analysis(content: str, observer: ExecutionObserver) -> ToolResult:
    """Extract business rules, actors, workflows, and integrations from FRS content."""
    system = (
        "You are a business requirements analyst. Extract structured information from "
        "Functional Requirements Specification content. "
        "Return JSON with: business_rules (list), actors (list), workflows (list), integrations (list)."
    )
    template = (
        "Extract the following from this FRS content:\n"
        "1. BUSINESS RULES: Key business rules and logic\n"
        "2. ACTORS: Who interacts with the system\n"
        "3. WORKFLOWS: Key process flows described\n"
        "4. INTEGRATIONS: Systems that integrate\n\n"
        "Content:\n{content}\n\n"
        "Return as JSON wrapped in ```json ... ``` tags."
    )
    return await _execute_llm_analysis_tool("frs_analysis", content, system, template, observer)


async def _execute_risk_analysis(content: str, observer: ExecutionObserver) -> ToolResult:
    """Extract risks with likelihood, impact, severity, and mitigation."""
    system = (
        "You are a risk analyst. Extract risks from content with likelihood, impact, severity, and mitigation. "
        "Return JSON array of risk objects: risk, likelihood (Low/Medium/High), impact (Low/Medium/High), "
        "severity (Low/Medium/High), mitigation, owner."
    )
    template = (
        "Extract all risks from the following content:\n\n{content}\n\n"
        "For each risk, provide: risk description, likelihood, impact, severity, mitigation, and owner. "
        "Return as JSON array wrapped in ```json ... ``` tags."
    )
    return await _execute_llm_analysis_tool("risk_analysis", content, system, template, observer)


async def _execute_action_extraction(content: str, observer: ExecutionObserver) -> ToolResult:
    """Extract action items with owners, due dates, and priorities."""
    system = (
        "You are a project coordinator. Extract action items from content. "
        "Return JSON array: action, owner, due_date, priority (High/Medium/Low), status."
    )
    template = (
        "Extract all action items from the following content:\n\n{content}\n\n"
        "For each action item, provide: action description, owner, due date, priority, and status. "
        "If owner or due date is not specified, mark as 'Not specified'. "
        "Return as JSON array wrapped in ```json ... ``` tags."
    )
    return await _execute_llm_analysis_tool("action_extraction", content, system, template, observer)


async def _execute_decision_extraction(content: str, observer: ExecutionObserver) -> ToolResult:
    """Extract decisions with who made them and rationale."""
    system = (
        "You are a meeting analyst. Extract decisions from content. "
        "Return JSON array: decision, made_by, rationale, date."
    )
    template = (
        "Extract all decisions made from the following content:\n\n{content}\n\n"
        "For each decision, provide: what was decided, who made it, rationale, and date. "
        "Return as JSON array wrapped in ```json ... ``` tags."
    )
    return await _execute_llm_analysis_tool("decision_extraction", content, system, template, observer)


async def _execute_workflow_extraction(content: str, observer: ExecutionObserver) -> ToolResult:
    """Extract workflow steps, actors, inputs, outputs, and business rules."""
    system = (
        "You are a business process analyst. Extract workflow information from content. "
        "Return JSON with: steps (array of {step, description, actor, system, decision}), "
        "actors (list), business_rules (list)."
    )
    template = (
        "Extract the workflow from the following content:\n\n{content}\n\n"
        "Provide:\n"
        "1. STEPS: Each step with description, actor, system, decision point\n"
        "2. ACTORS: All roles involved\n"
        "3. BUSINESS RULES: Rules governing the workflow\n"
        "Return as JSON wrapped in ```json ... ``` tags."
    )
    return await _execute_llm_analysis_tool("workflow_extraction", content, system, template, observer)


async def _execute_entity_extraction(content: str, observer: ExecutionObserver) -> ToolResult:
    """Extract entities, topics, and systems from content."""
    system = (
        "You are a knowledge extraction specialist. Extract entities from content. "
        "Return JSON with: entities (list), topics (list), systems (list), "
        "departments (list), people (list), locations (list)."
    )
    template = (
        "Extract all entities from the following content:\n\n{content}\n\n"
        "Categories: entities, topics, systems, departments, people, locations. "
        "Return as JSON wrapped in ```json ... ``` tags."
    )
    return await _execute_llm_analysis_tool("entity_extraction", content, system, template, observer)


async def _execute_document_compare(
    content_a: str,
    content_b: str,
    observer: ExecutionObserver,
) -> ToolResult:
    """Compare two documents and extract similarities, differences, gaps, and recommendations."""
    observer.start_tool("document_compare")
    start = time.time()

    system = (
        "You are a document comparison analyst. Compare two documents and extract "
        "similarities, differences, gaps, and recommendations. "
        "Return JSON with: similarities (list), differences (list), gaps (list), recommendations (list)."
    )
    user_prompt = (
        f"Compare the following two documents:\n\n"
        f"DOCUMENT A:\n{content_a[:6000]}\n\n"
        f"DOCUMENT B:\n{content_b[:6000]}\n\n"
        f"Extract:\n"
        f"1. SIMILARITIES: What they have in common\n"
        f"2. DIFFERENCES: Where they differ\n"
        f"3. GAPS: What is missing in one but present in the other\n"
        f"4. RECOMMENDATIONS: Suggested actions\n\n"
        f"Return as JSON wrapped in ```json ... ``` tags."
    )

    try:
        response = await _call_llm(system, user_prompt)
        structured = None
        if response:
            import re
            json_match = re.search(r"```json\n(.*?)\n```", response, re.DOTALL)
            if json_match:
                structured = json.loads(json_match.group(1))

        elapsed_ms = (time.time() - start) * 1000
        observer.finish_tool("document_compare", {"has_result": structured is not None})
        return ToolResult(
            tool_name="document_compare",
            success=True,
            result=structured or {"raw_response": response},
            execution_ms=elapsed_ms,
        )
    except Exception as e:
        elapsed_ms = (time.time() - start) * 1000
        observer.fail_tool("document_compare", str(e))
        return ToolResult(
            tool_name="document_compare",
            success=False,
            result=None,
            execution_ms=elapsed_ms,
            error=str(e),
        )


async def _execute_document_summary(content: str, observer: ExecutionObserver) -> ToolResult:
    """Generate an executive summary from content."""
    system = (
        "You are an executive summarizer. Generate a concise executive summary with: "
        "OVERVIEW (1-2 sentences), KEY FINDINGS (bullets), SYSTEMS (key systems), CONCLUSION. "
        "Return as JSON wrapped in ```json ... ``` tags."
    )
    template = (
        "Generate an executive summary from the following content:\n\n{content}\n\n"
        "Include: OVERVIEW, KEY FINDINGS, SYSTEMS, CONCLUSION. "
        "Return as JSON wrapped in ```json ... ``` tags."
    )
    return await _execute_llm_analysis_tool("document_summary", content, system, template, observer)


async def _execute_meeting_analysis(
    transcript: str,
    observer: ExecutionObserver,
) -> ToolResult:
    """Analyze a meeting transcript and generate structured report."""
    observer.start_tool("meeting_analysis")
    start = time.time()

    system = (
        "You are a meeting analyst. Generate a structured meeting report from a transcript. "
        "Return JSON with: summary (str), participants (list), discussion_points (list), "
        "decisions (list of {decision, made_by, rationale}), "
        "action_items (list of {action, owner, due_date, priority}), "
        "risks (list of {risk, likelihood, impact, mitigation}), "
        "follow_ups (list)."
    )

    try:
        response = await _call_llm(
            system,
            f"Generate a meeting report from this transcript:\n\n{transcript[:10000]}",
        )
        structured = None
        if response:
            import re
            json_match = re.search(r"```json\n(.*?)\n```", response, re.DOTALL)
            if json_match:
                structured = json.loads(json_match.group(1))

        elapsed_ms = (time.time() - start) * 1000
        observer.finish_tool("meeting_analysis", {"has_report": structured is not None})
        return ToolResult(
            tool_name="meeting_analysis",
            success=True,
            result=structured or {"raw_report": response},
            execution_ms=elapsed_ms,
        )
    except Exception as e:
        elapsed_ms = (time.time() - start) * 1000
        observer.fail_tool("meeting_analysis", str(e))
        return ToolResult(
            tool_name="meeting_analysis",
            success=False,
            result=None,
            execution_ms=elapsed_ms,
            error=str(e),
        )


async def _execute_audio_analysis(
    transcript: str,
    observer: ExecutionObserver,
) -> ToolResult:
    """Analyze audio recording transcript for speakers, topics, and structure."""
    observer.start_tool("audio_analysis")
    start = time.time()

    system = (
        "You are an audio recording analyst. Analyze a transcript for structure and content. "
        "Return JSON with: summary (str), speakers (list), topics (list), "
        "duration_minutes (int if available), key_points (list)."
    )

    try:
        response = await _call_llm(
            system,
            f"Analyze this audio recording transcript:\n\n{transcript[:8000]}",
        )
        structured = None
        if response:
            import re
            json_match = re.search(r"```json\n(.*?)\n```", response, re.DOTALL)
            if json_match:
                structured = json.loads(json_match.group(1))

        elapsed_ms = (time.time() - start) * 1000
        observer.finish_tool("audio_analysis", {"has_analysis": structured is not None})
        return ToolResult(
            tool_name="audio_analysis",
            success=True,
            result=structured or {"raw_analysis": response},
            execution_ms=elapsed_ms,
        )
    except Exception as e:
        elapsed_ms = (time.time() - start) * 1000
        observer.fail_tool("audio_analysis", str(e))
        return ToolResult(
            tool_name="audio_analysis",
            success=False,
            result=None,
            execution_ms=elapsed_ms,
            error=str(e),
        )


# ── Dispatch Map ─────────────────────────────────────────────────────────

_TOOL_DISPATCH: dict[str, Any] = {
    "rag_search": _execute_rag_search,
    "policy_analysis": _execute_policy_analysis,
    "frs_analysis": _execute_frs_analysis,
    "risk_analysis": _execute_risk_analysis,
    "action_extraction": _execute_action_extraction,
    "decision_extraction": _execute_decision_extraction,
    "workflow_extraction": _execute_workflow_extraction,
    "entity_extraction": _execute_entity_extraction,
    "document_compare": _execute_document_compare,
    "document_summary": _execute_document_summary,
    "meeting_analysis": _execute_meeting_analysis,
    "audio_analysis": _execute_audio_analysis,
}


# ── Tool Name → Evidence Field Mapping ────────────────────────────────────
# Maps tool names to the EvidenceBundle fields they populate.

_EVIDENCE_MAPPING: dict[str, list[str]] = {
    "rag_search": ["sources", "rag_context"],
    "policy_analysis": ["policy_analysis"],
    "frs_analysis": ["policy_analysis"],  # Reuses policy_analysis slot, but stores FRS data
    "risk_analysis": ["risks"],
    "action_extraction": ["actions"],
    "decision_extraction": ["decisions"],
    "workflow_extraction": ["workflows"],
    "entity_extraction": ["entities"],
    "document_compare": ["comparison"],
    "document_summary": ["summary"],
    "meeting_analysis": ["meeting_report", "decisions", "actions", "risks"],
    "audio_analysis": ["audio_analysis"],
}


def _apply_tool_to_evidence(result: ToolResult, bundle: EvidenceBundle) -> None:
    """Route a successful tool result into the appropriate EvidenceBundle fields."""
    if not result.success or not result.result:
        return

    tool = result.tool_name
    data = result.result

    if tool == "rag_search":
        citations = data.get("citations", [])
        bundle.sources.extend(citations)
        bundle.rag_context = data.get("context")

    elif tool == "policy_analysis":
        bundle.policy_analysis = {
            "obligations": data.get("obligations", []),
            "controls": data.get("controls", []),
            "risks": data.get("risks", []),
        }

    elif tool == "frs_analysis":
        bundle.policy_analysis = {
            "business_rules": data.get("business_rules", []),
            "actors": data.get("actors", []),
            "workflows": data.get("workflows", []),
            "integrations": data.get("integrations", []),
        }

    elif tool == "risk_analysis":
        if isinstance(data, list):
            bundle.risks.extend(data)
        elif isinstance(data, dict):
            bundle.risks.append(data)

    elif tool == "action_extraction":
        if isinstance(data, list):
            bundle.actions.extend(data)
        elif isinstance(data, dict) and "action_items" in data:
            bundle.actions.extend(data["action_items"])

    elif tool == "decision_extraction":
        if isinstance(data, list):
            bundle.decisions.extend(data)
        elif isinstance(data, dict) and "decisions" in data:
            bundle.decisions.extend(data["decisions"])

    elif tool == "workflow_extraction":
        bundle.workflows.append(data)

    elif tool == "entity_extraction":
        if isinstance(data, dict):
            bundle.entities.extend(data.get("entities", []))
            # Also store full entity data for context building
            result.metadata["full_entity_data"] = {
                "topics": data.get("topics", []),
                "systems": data.get("systems", []),
                "departments": data.get("departments", []),
            }

    elif tool == "document_compare":
        bundle.comparison = data

    elif tool == "document_summary":
        bundle.summary = data.get("summary") or data.get("overview") or str(data)

    elif tool == "meeting_analysis":
        bundle.meeting_report = data
        if isinstance(data, dict):
            if data.get("decisions"):
                bundle.decisions.extend(
                    d if isinstance(d, dict) else {"decision": str(d)}
                    for d in data["decisions"]
                )
            if data.get("action_items"):
                bundle.actions.extend(
                    a if isinstance(a, dict) else {"action": str(a)}
                    for a in data["action_items"]
                )
            if data.get("risks"):
                bundle.risks.extend(
                    r if isinstance(r, dict) else {"risk": str(r)}
                    for r in data["risks"]
                )
        bundle.summary = bundle.summary or (data.get("summary") if isinstance(data, dict) else str(data))

    elif tool == "audio_analysis":
        bundle.audio_analysis = data


# ── Public API ───────────────────────────────────────────────────────────

async def execute_plan(
    plan: Any,
    user_query: str,
    db: Any,
    observer: Optional[ExecutionObserver] = None,
    project_ids: Optional[list[int]] = None,
    document_id: Optional[str] = None,
    session_state: Optional[dict] = None,
    content_source: Optional[str] = None,
    skip_tools: Optional[list[str]] = None,
) -> EvidenceBundle:
    """
    Execute the tools in an execution plan and collect evidence.

    Accepts both ExecutionPlan objects and dict representations
    (from ResponseStrategy.execution_plan).

    Parameters
    ----------
    plan : ExecutionPlan or dict
        The plan to execute. Can be an ExecutionPlan object or a dict
        with 'tools', 'intent', 'estimated_steps', etc.
    user_query : str
        The original user query.
    db : AsyncSession
        Database session for RAG queries.
    observer : ExecutionObserver or None
        Tracks execution timing and results. If None, a new one is created.
    project_ids : list[int] or None
        Project IDs for RAG search scope.
    document_id : str or None
        Specific document ID to scope RAG search.
    session_state : dict or None
        Session state with audio context (transcript, etc.).
    content_source : str or None
        Pre-existing content to analyze (e.g., an already-retrieved document text).
    skip_tools : list[str] or None
        List of tool names to skip (e.g., ['rag_search'] when RAG already done).

    Returns
    -------
    EvidenceBundle
        All evidence collected from tool execution.
    """
    if observer is None:
        observer = ExecutionObserver()

    bundle = EvidenceBundle()
    observer.start_tool("execute_plan")

    # Normalize plan to dict form
    if isinstance(plan, ExecutionPlan):
        plan_dict = plan.to_dict()
    elif isinstance(plan, dict):
        plan_dict = plan
    else:
        logger.warning("[TOOL_EXEC] Invalid plan type: %s — skipping execution", type(plan).__name__)
        observer.finish_tool("execute_plan", {"error": "invalid_plan"})
        return bundle

    tools = plan_dict.get("tools", [])
    intent = plan_dict.get("intent", "unknown")
    skip = set(skip_tools or [])

    logger.info(
        "[TOOL_EXEC] Executing plan: %d tools, intent=%s, query=%r, skip=%s",
        len(tools), intent, user_query[:80], skip,
    )

    current_content = content_source

    for tool_spec in tools:
        tool_name = tool_spec["tool"]
        tool_str = tool_name.value if hasattr(tool_name, "value") else str(tool_name)

        # Skip tools in the skip list
        if tool_str in skip:
            logger.info("[TOOL_EXEC] Skipping tool: %s (in skip list)", tool_str)
            continue

        is_optional = tool_spec.get("optional", False)
        logger.info("[TOOL_EXEC] Running tool: %s (optional=%s)", tool_str, is_optional)

        # Dispatch to the appropriate executor
        if tool_str == "rag_search":
            result = await _execute_rag_search(
                user_query,
                project_ids or [],
                db,
                observer,
                document_id=document_id,
            )
            if result.success and result.result:
                bundle.rag_context = result.result.get("context")
                bundle.sources.extend(result.result.get("citations", []))
                # Use RAG answer as content for subsequent tools
                answer_text = result.result.get("answer_text", "")
                if answer_text and not current_content:
                    current_content = answer_text

        elif tool_str in _TOOL_DISPATCH:
            executor = _TOOL_DISPATCH[tool_str]
            # Determine content for analysis tools
            content_to_analyze = current_content or bundle.rag_context or user_query

            if tool_str == "document_compare":
                # Document compare needs two content sources
                # For now, use the same content split (A = RAG context, B = user query context)
                result = await executor(content_to_analyze, user_query, observer)
            elif tool_str in ("meeting_analysis", "audio_analysis"):
                # Use session transcript if available
                transcript = None
                if session_state:
                    transcript = session_state.get("current_transcript")
                content_to_analyze = transcript or content_to_analyze
                if tool_str == "meeting_analysis":
                    result = await executor(content_to_analyze, observer)
                else:
                    result = await executor(content_to_analyze, observer)
            else:
                result = await executor(content_to_analyze, observer)

            # Apply result to evidence bundle
            _apply_tool_to_evidence(result, bundle)

        elif tool_str == "chat" or tool_str == "query_rewrite":
            # These are handled at the response strategy level, not here
            logger.info("[TOOL_EXEC] Skipping %s — handled at response layer", tool_str)
            continue

        else:
            logger.warning("[TOOL_EXEC] Unknown tool: %s — skipping", tool_str)

        bundle.add_result(result)

        # Error tolerance: if non-optional tool fails, log warning but continue
        if not result.success and not is_optional:
            logger.warning(
                "[TOOL_EXEC] Non-optional tool %s failed: %s. Continuing with partial evidence.",
                tool_str, result.error,
            )

    logger.info(
        "[TOOL_EXEC] Plan execution complete: %d/%d tools succeeded",
        sum(1 for r in bundle.results if r.success),
        len(bundle.results),
    )

    observer.finish_tool("execute_plan", bundle.to_dict())

    # Attach observer summary to plan for frontend display
    plan.execution_metadata = observer.summary()

    return bundle


async def execute_and_build_context(
    plan: ExecutionPlan,
    user_query: str,
    db: Any,
    project_ids: Optional[list[int]] = None,
    document_id: Optional[str] = None,
    session_state: Optional[dict] = None,
) -> tuple[EvidenceBundle, str, ExecutionObserver]:
    """
    Execute the plan and build the context string for the LLM.

    Convenience wrapper that:
    1. Creates an ExecutionObserver
    2. Executes the plan
    3. Builds a consolidated context string
    4. Returns the bundle, context string, and observer

    Returns
    -------
    tuple[EvidenceBundle, str, ExecutionObserver]
        (evidence_bundle, context_string, observer)
    """
    observer = ExecutionObserver()
    bundle = await execute_plan(
        plan=plan,
        user_query=user_query,
        db=db,
        observer=observer,
        project_ids=project_ids,
        document_id=document_id,
        session_state=session_state,
    )
    context = bundle.build_context_string()
    return bundle, context, observer
