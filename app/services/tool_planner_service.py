"""
tool_planner_service.py — DocTel Tool Planning Layer

Sits between Intent Detection and Response Strategy.
Determines HOW the system solves a task — which knowledge tools
to use, in what order, and what the execution plan looks like.

Architecture:

Intent
  ↓
Task Planner (this service)
  ↓
Tool Selection
  ↓
Execution Plan
  ↓
Evidence Collection
  ↓
Response Strategy
  ↓
Output
"""
from __future__ import annotations

import logging
import time
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ── Tool Types ───────────────────────────────────────────────────────────

class ToolType(str, Enum):
    """Available knowledge tools the planner can select."""
    RAG_SEARCH = "rag_search"
    DOCUMENT_COMPARE = "document_compare"
    DOCUMENT_SUMMARY = "document_summary"
    POLICY_ANALYSIS = "policy_analysis"
    FRS_ANALYSIS = "frs_analysis"
    RISK_ANALYSIS = "risk_analysis"
    ACTION_EXTRACTION = "action_extraction"
    DECISION_EXTRACTION = "decision_extraction"
    WORKFLOW_EXTRACTION = "workflow_extraction"
    DIAGRAM_GENERATION = "diagram_generation"
    MEETING_ANALYSIS = "meeting_analysis"
    AUDIO_ANALYSIS = "audio_analysis"
    VIDEO_ANALYSIS = "video_analysis"
    CSV_ANALYSIS = "csv_analysis"
    DATABASE_QUERY = "database_query"
    REPORT_GENERATION = "report_generation"
    KNOWLEDGE_GRAPH_QUERY = "knowledge_graph_query"
    KNOWLEDGE_GRAPH = "knowledge_graph_search"
    TIMELINE_GENERATION = "timeline_generation"
    ENTITY_EXTRACTION = "entity_extraction"
    KNOWLEDGE_ASSET = "knowledge_asset_search"  # Search + discover knowledge assets
    KNOWLEDGE_SPACE = "knowledge_space_search"  # Search + discover knowledge spaces
    QUERY_REWRITE = "query_rewrite"
    CHAT = "chat"


# ── Execution Plan ───────────────────────────────────────────────────────

class ExecutionPlan:
    """
    A complete execution plan for a single user query.

    Fields
    ------
    intent : str
        The detected KnowledgeIntent value.
    tools : list[dict]
        List of tool specifications in execution order.
        Each tool dict: { "tool": ToolType, "purpose": str, "optional": bool }
    estimated_steps : int
        Number of execution steps.
    render_hint : str
        Frontend rendering hint from response strategy.
    citation_mode : str
        Citation display mode.
    strategy_summary : str
        Human-readable description of the plan.
    execution_metadata : dict
        Runtime observability data (tool start times, durations, results).
    """

    def __init__(
        self,
        intent: str,
        tools: list[dict[str, Any]],
        estimated_steps: int,
        render_hint: str = "narrative",
        citation_mode: str = "full",
        strategy_summary: str = "",
        execution_metadata: Optional[dict[str, Any]] = None,
    ):
        self.intent = intent
        self.tools = tools
        self.estimated_steps = estimated_steps
        self.render_hint = render_hint
        self.citation_mode = citation_mode
        self.strategy_summary = strategy_summary or self._default_summary()
        self.execution_metadata = execution_metadata or {}

    def _default_summary(self) -> str:
        count = len(self.tools)
        names = [t["tool"] if isinstance(t, dict) else str(t) for t in self.tools]
        return f"Plan: {count} tool{'s' if count != 1 else ''} — {' → '.join(names)}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "tools": [
                {k: v.value if isinstance(v, Enum) else v for k, v in t.items()}
                for t in self.tools
            ],
            "estimated_steps": self.estimated_steps,
            "render_hint": self.render_hint,
            "citation_mode": self.citation_mode,
            "strategy_summary": self.strategy_summary,
            "execution_metadata": self.execution_metadata,
        }

    def tool_names(self) -> list[str]:
        """Return human-readable tool names for this plan."""
        return [
            t["tool"].replace("_", " ").title() if isinstance(t, dict) else str(t)
            for t in self.tools
        ]

    def has_tool(self, tool_type: ToolType) -> bool:
        """Check if a specific tool is in the plan."""
        return any(
            t.get("tool") == tool_type or t.get("tool") == tool_type.value
            for t in self.tools
        )


# ── Tool → Intent Mapping ───────────────────────────────────────────────
# Maps each KnowledgeIntent to the tools it requires.

_INTENT_TOOL_MAP: dict[str, list[dict[str, Any]]] = {
    "question_answering": [
        {"tool": ToolType.QUERY_REWRITE, "purpose": "Rewrite follow-up query with context", "optional": False},
        {"tool": ToolType.RAG_SEARCH, "purpose": "Search knowledge base for relevant chunks", "optional": False},
        {"tool": ToolType.CHAT, "purpose": "Generate answer from evidence", "optional": False},
    ],
    "executive_summary": [
        {"tool": ToolType.RAG_SEARCH, "purpose": "Search knowledge base for key content", "optional": False},
        {"tool": ToolType.DOCUMENT_SUMMARY, "purpose": "Generate executive summary", "optional": False},
    ],
    "document_analysis": [
        {"tool": ToolType.RAG_SEARCH, "purpose": "Search for document content", "optional": False},
        {"tool": ToolType.ENTITY_EXTRACTION, "purpose": "Extract key entities and topics", "optional": False},
        {"tool": ToolType.CHAT, "purpose": "Synthesize analysis findings", "optional": False},
    ],
    "policy_review": [
        {"tool": ToolType.RAG_SEARCH, "purpose": "Fetch relevant policy sections", "optional": False},
        {"tool": ToolType.POLICY_ANALYSIS, "purpose": "Analyze obligations, controls, risks", "optional": False},
        {"tool": ToolType.RISK_ANALYSIS, "purpose": "Assess compliance and operational risks", "optional": True},
    ],
    "frs_analysis": [
        {"tool": ToolType.RAG_SEARCH, "purpose": "Fetch FRS sections", "optional": False},
        {"tool": ToolType.FRS_ANALYSIS, "purpose": "Extract business rules and actors", "optional": False},
        {"tool": ToolType.WORKFLOW_EXTRACTION, "purpose": "Map business workflows", "optional": True},
    ],
    "meeting_analysis": [
        {"tool": ToolType.RAG_SEARCH, "purpose": "Fetch meeting transcript/notes", "optional": True},
        {"tool": ToolType.AUDIO_ANALYSIS, "purpose": "Analyze audio recording if available", "optional": True},
        {"tool": ToolType.DECISION_EXTRACTION, "purpose": "Extract decisions made", "optional": False},
        {"tool": ToolType.ACTION_EXTRACTION, "purpose": "Extract action items", "optional": False},
        {"tool": ToolType.MEETING_ANALYSIS, "purpose": "Generate structured meeting report", "optional": False},
    ],
    "risk_assessment": [
        {"tool": ToolType.RAG_SEARCH, "purpose": "Fetch risk-related content", "optional": False},
        {"tool": ToolType.RISK_ANALYSIS, "purpose": "Identify and assess risks", "optional": False},
    ],
    "action_extraction": [
        {"tool": ToolType.RAG_SEARCH, "purpose": "Fetch relevant content", "optional": False},
        {"tool": ToolType.ACTION_EXTRACTION, "purpose": "Extract action items with owners", "optional": False},
        {"tool": ToolType.DECISION_EXTRACTION, "purpose": "Extract related decisions", "optional": True},
    ],
    "workflow_extraction": [
        {"tool": ToolType.RAG_SEARCH, "purpose": "Fetch process-related content", "optional": False},
        {"tool": ToolType.WORKFLOW_EXTRACTION, "purpose": "Extract workflow steps", "optional": False},
        {"tool": ToolType.DIAGRAM_GENERATION, "purpose": "Generate process diagram", "optional": True},
    ],
    "process_diagram": [
        {"tool": ToolType.RAG_SEARCH, "purpose": "Fetch content to visualize", "optional": True},
        {"tool": ToolType.WORKFLOW_EXTRACTION, "purpose": "Extract steps and actors", "optional": False},
        {"tool": ToolType.DIAGRAM_GENERATION, "purpose": "Generate Mermaid/BPMN diagram", "optional": False},
    ],
    "comparison": [
        {"tool": ToolType.DOCUMENT_COMPARE, "purpose": "Compare two or more documents", "optional": False},
        {"tool": ToolType.RAG_SEARCH, "purpose": "Search for additional context", "optional": True},
    ],
    "root_cause_analysis": [
        {"tool": ToolType.RAG_SEARCH, "purpose": "Fetch relevant content", "optional": False},
        {"tool": ToolType.RISK_ANALYSIS, "purpose": "Identify contributing factors", "optional": False},
    ],
    "data_analysis": [
        {"tool": ToolType.RAG_SEARCH, "purpose": "Fetch data descriptions", "optional": True},
        {"tool": ToolType.CSV_ANALYSIS, "purpose": "Analyze tabular data", "optional": True},
        {"tool": ToolType.DATABASE_QUERY, "purpose": "Query structured sources", "optional": True},
        {"tool": ToolType.REPORT_GENERATION, "purpose": "Generate insights report", "optional": False},
    ],
    "csv_analysis": [
        {"tool": ToolType.CSV_ANALYSIS, "purpose": "Analyze CSV columns and data", "optional": False},
        {"tool": ToolType.REPORT_GENERATION, "purpose": "Generate data insights report", "optional": False},
    ],
    "database_analysis": [
        {"tool": ToolType.DATABASE_QUERY, "purpose": "Query database schema and data", "optional": False},
        {"tool": ToolType.REPORT_GENERATION, "purpose": "Generate database insights", "optional": False},
    ],
    "report_generation": [
        {"tool": ToolType.RAG_SEARCH, "purpose": "Gather source material", "optional": True},
        {"tool": ToolType.REPORT_GENERATION, "purpose": "Generate structured report", "optional": False},
    ],
    "dashboard_generation": [
        {"tool": ToolType.RAG_SEARCH, "purpose": "Gather data sources", "optional": True},
        {"tool": ToolType.DATABASE_QUERY, "purpose": "Query KPIs and metrics", "optional": True},
        {"tool": ToolType.REPORT_GENERATION, "purpose": "Generate dashboard report", "optional": False},
    ],
    "knowledge_discovery": [
        {"tool": ToolType.KNOWLEDGE_SPACE, "purpose": "Search knowledge spaces for relevant context", "optional": False},
        {"tool": ToolType.KNOWLEDGE_GRAPH, "purpose": "Search knowledge graph for entity relationships", "optional": False},
        {"tool": ToolType.KNOWLEDGE_ASSET, "purpose": "Search knowledge assets across all types", "optional": False},
        {"tool": ToolType.RAG_SEARCH, "purpose": "Search document chunks for specific details", "optional": True},
        {"tool": ToolType.ENTITY_EXTRACTION, "purpose": "Extract entities and relationships", "optional": False},
    ],
    "image_analysis": [
        {"tool": ToolType.RAG_SEARCH, "purpose": "Find related document context", "optional": True},
    ],
    "audio_analysis": [
        {"tool": ToolType.AUDIO_ANALYSIS, "purpose": "Analyze audio recording", "optional": False},
        {"tool": ToolType.MEETING_ANALYSIS, "purpose": "Generate meeting report if applicable", "optional": True},
        {"tool": ToolType.ACTION_EXTRACTION, "purpose": "Extract action items", "optional": True},
        {"tool": ToolType.DECISION_EXTRACTION, "purpose": "Extract decisions", "optional": True},
    ],
    "chat": [
        {"tool": ToolType.QUERY_REWRITE, "purpose": "Rewrite query with conversation context", "optional": True},
        {"tool": ToolType.RAG_SEARCH, "purpose": "Search knowledge base", "optional": True},
        {"tool": ToolType.CHAT, "purpose": "Generate natural response", "optional": False},
    ],
}


# ── Context Adjustments ─────────────────────────────────────────────────
# These modifiers adjust the plan based on available context.

_CONTEXT_ADJUSTMENTS: dict[str, dict[str, Any]] = {
    "has_audio_context": {
        "add_tools": [
            {"tool": ToolType.AUDIO_ANALYSIS, "purpose": "Analyze attached audio recording", "optional": False},
            {"tool": ToolType.MEETING_ANALYSIS, "purpose": "Generate meeting insights from audio", "optional": True},
        ],
        "remove_tools": [],
        "modify_rag": "session_only",
    },
    "no_rag_context": {
        "add_tools": [{"tool": ToolType.KNOWLEDGE_ASSET, "purpose": "Search across all knowledge asset types", "optional": False}],
        "remove_tools": [ToolType.RAG_SEARCH, ToolType.DOCUMENT_COMPARE],
        "modify_rag": None,
    },
    "has_knowledge_assets": {
        "add_tools": [{"tool": ToolType.KNOWLEDGE_ASSET, "purpose": "Search knowledge assets for relevant content", "optional": True}],
        "remove_tools": [],
        "modify_rag": None,
    },
    "has_knowledge_spaces": {
        "add_tools": [{"tool": ToolType.KNOWLEDGE_SPACE, "purpose": "Search knowledge spaces for relevant context", "optional": False}],
        "remove_tools": [],
        "modify_rag": None,
    },
    "has_agent_memory": {
        "add_tools": [{"tool": ToolType.KNOWLEDGE_ASSET, "purpose": "Discover knowledge assets via agent runtime", "optional": True}],
        "remove_tools": [],
        "modify_rag": None,
    },
    "document_type_policy": {
        "add_tools": [{"tool": ToolType.POLICY_ANALYSIS, "purpose": "Analyze policy content", "optional": False}],
        "remove_tools": [],
        "modify_rag": None,
    },
    "document_type_frs": {
        "add_tools": [{"tool": ToolType.FRS_ANALYSIS, "purpose": "Analyze FRS content", "optional": False}],
        "remove_tools": [],
        "modify_rag": None,
    },
    "document_type_meeting": {
        "add_tools": [
            {"tool": ToolType.DECISION_EXTRACTION, "purpose": "Extract decisions from meeting", "optional": False},
            {"tool": ToolType.ACTION_EXTRACTION, "purpose": "Extract action items from meeting", "optional": False},
        ],
        "remove_tools": [],
        "modify_rag": None,
    },
}


def _apply_context_adjustments(
    tools: list[dict[str, Any]],
    intent: str,
    has_audio_context: bool = False,
    has_rag_context: bool = True,
    has_knowledge_spaces: bool = False,
    has_agent_memory: bool = False,
    document_type: Optional[str] = None,
    asset_types: Optional[list[str]] = None,
) -> list[dict[str, Any]]:
    """Apply context-specific adjustments to the tool list.

    Parameters
    ----------
    tools : list[dict]
        Base tool list for the intent.
    intent : str
        The detected KnowledgeIntent.
    has_audio_context : bool
        Whether audio recording is in session.
    has_rag_context : bool
        Whether vector store retrieval is available.
    has_knowledge_spaces : bool
        Whether knowledge spaces are available and should be searched.
    has_agent_memory : bool
        Whether the agent memory runtime is available for multi-agent
        coordination. When True, adds KNOWLEDGE_ASSET discovery tool.
    document_type : str or None
        Document type classification.
    asset_types : list[str] or None
        Knowledge asset types found during discovery (e.g. ["audio", "csv", "document"]).
        When present, adds KNOWLEDGE_ASSET tool so the plan includes asset search.
    """
    adjusted = list(tools)

    # Knowledge asset types found — add KNOWLEDGE_ASSET tool for asset-aware planning
    if asset_types:
        # Map asset types to their analysis tools
        _ASSET_TO_TOOL = {
            "audio": (ToolType.AUDIO_ANALYSIS, "Analyze audio recording"),
            "video": (ToolType.VIDEO_ANALYSIS, "Analyze video recording with frame analysis"),
            "csv": (ToolType.CSV_ANALYSIS, "Analyze CSV data"),
            "image": (ToolType.RAG_SEARCH, "Find related document context for image"),
            "database": (ToolType.DATABASE_QUERY, "Query connected database"),
            "api": (ToolType.RAG_SEARCH, "Fetch API documentation"),
            "connector": (ToolType.RAG_SEARCH, "Fetch connector documentation"),
            "document": (ToolType.RAG_SEARCH, "Search within document assets"),
        }
        for atype in asset_types:
            if atype in _ASSET_TO_TOOL:
                tool_type, purpose = _ASSET_TO_TOOL[atype]
                if not any(
                    t["tool"] == tool_type and t.get("purpose", "") == purpose
                    for t in adjusted
                ):
                    adjusted.append({"tool": tool_type, "purpose": purpose, "optional": True})
        # Ensure KNOWLEDGE_ASSET tool is available for cross-type discovery
        if not any(t["tool"] == ToolType.KNOWLEDGE_ASSET for t in adjusted):
            adjusted.append({"tool": ToolType.KNOWLEDGE_ASSET, "purpose": "Search all knowledge asset types", "optional": True})

        # Add KNOWLEDGE_SPACE tool for space-aware planning when assets found
        if not any(t["tool"] == ToolType.KNOWLEDGE_SPACE for t in adjusted):
            adjusted.append({"tool": ToolType.KNOWLEDGE_SPACE, "purpose": "Search knowledge spaces for relevant context", "optional": True})

    # Audio context
    if has_audio_context:
        adj = _CONTEXT_ADJUSTMENTS["has_audio_context"]
        adjusted.extend(adj["add_tools"])
        adjusted = [t for t in adjusted if t["tool"] not in adj["remove_tools"]]
        if intent not in ("policy_review", "frs_analysis", "comparison", "root_cause_analysis"):
            for t in adjusted:
                if t["tool"] == ToolType.RAG_SEARCH:
                    t["optional"] = True
                    break

    # Knowledge spaces context
    if has_knowledge_spaces:
        adj = _CONTEXT_ADJUSTMENTS["has_knowledge_spaces"]
        adjusted.extend(adj["add_tools"])

    # Agent memory context
    if has_agent_memory:
        adj = _CONTEXT_ADJUSTMENTS["has_agent_memory"]
        adjusted.extend(adj["add_tools"])

    # No RAG context
    if not has_rag_context:
        adj = _CONTEXT_ADJUSTMENTS["no_rag_context"]
        adjusted = [t for t in adjusted if t["tool"] not in adj["remove_tools"]]

    # Document type adjustments
    if document_type:
        dt_key = f"document_type_{document_type}"
        if dt_key in _CONTEXT_ADJUSTMENTS:
            adj = _CONTEXT_ADJUSTMENTS[dt_key]
            adjusted.extend(adj["add_tools"])

    # Deduplicate tools (keep first occurrence)
    seen_tools: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for t in adjusted:
        tool_val = t["tool"].value if isinstance(t["tool"], Enum) else t["tool"]
        if tool_val not in seen_tools:
            seen_tools.add(tool_val)
            deduped.append(t)
        else:
            # If first occurrence was optional and new one is required, upgrade
            for existing in deduped:
                existing_val = existing["tool"].value if isinstance(existing["tool"], Enum) else existing["tool"]
                if existing_val == tool_val and existing.get("optional", True) and not t.get("optional", True):
                    existing["optional"] = False
                    existing["purpose"] = t.get("purpose", existing.get("purpose", ""))

    return deduped


# ── Plan Execution ───────────────────────────────────────────────────────

class ExecutionObserver:
    """Tracks execution time and results for observability."""

    def __init__(self):
        self._start_times: dict[str, float] = {}
        self._results: dict[str, Any] = {}
        self._errors: dict[str, str] = {}

    def start_tool(self, tool_name: str) -> None:
        """Record the start time of a tool execution."""
        self._start_times[tool_name] = time.time()
        logger.info("[EXEC_PLAN] Starting tool: %s", tool_name)

    def finish_tool(self, tool_name: str, result: Any = None) -> float:
        """Record the completion of a tool and return elapsed seconds."""
        start = self._start_times.pop(tool_name, time.time())
        elapsed = time.time() - start
        self._results[tool_name] = {
            "elapsed_sec": round(elapsed, 3),
            "result": result,
            "status": "completed",
        }
        logger.info("[EXEC_PLAN] Completed tool: %s in %.2fs", tool_name, elapsed)
        return elapsed

    def fail_tool(self, tool_name: str, error: str) -> None:
        """Record a tool failure."""
        start = self._start_times.pop(tool_name, time.time())
        elapsed = time.time() - start
        self._errors[tool_name] = error
        self._results[tool_name] = {
            "elapsed_sec": round(elapsed, 3),
            "result": None,
            "status": "failed",
            "error": error,
        }
        logger.warning("[EXEC_PLAN] Tool FAILED: %s — %s", tool_name, error)

    def summary(self) -> dict[str, Any]:
        """Return observability summary."""
        completed = sum(1 for v in self._results.values() if v.get("status") == "completed")
        failed = sum(1 for v in self._results.values() if v.get("status") == "failed")
        total_time = sum(v.get("elapsed_sec", 0) for v in self._results.values())
        return {
            "tools_executed": list(self._results.keys()),
            "completed": completed,
            "failed": failed,
            "total_time_sec": round(total_time, 3),
            "results": self._results,
            "errors": self._errors,
        }


# ── Public API ───────────────────────────────────────────────────────────

def plan_execution(
    intent: str,
    has_audio_context: bool = False,
    has_rag_context: bool = True,
    has_knowledge_spaces: bool = False,
    has_agent_memory: bool = False,
    document_type: Optional[str] = None,
    conversation_context: Optional[str] = None,
    observer: Optional[ExecutionObserver] = None,
    asset_types: Optional[list[str]] = None,
) -> ExecutionPlan:
    """
    Generate an ExecutionPlan for a given intent and context.

    This is the primary entry point for the tool planner. It:
    1. Looks up the tool list for the intent
    2. Applies context-specific adjustments
    3. Builds and returns the ExecutionPlan

    Parameters
    ----------
    intent : str
        The detected KnowledgeIntent value (e.g. "policy_review").
    has_audio_context : bool
        Whether an audio recording is attached to the session.
    has_rag_context : bool
        Whether vector store retrieval is available.
    has_knowledge_spaces : bool
        Whether knowledge spaces are available and should be searched.
    has_agent_memory : bool
        Whether the agent memory runtime is available for multi-agent
        coordination. When True, the planner adds a KNOWLEDGE_ASSET
        discovery tool so the plan includes agent-aware asset search.
    document_type : str or None
        The classified document type (e.g. "policy", "frs", "meeting").
    conversation_context : str or None
        Previous conversation context for follow-up disambiguation.
    observer : ExecutionObserver or None
        Optional observer for tracking execution.
    asset_types : list[str] or None
        Knowledge asset types discovered by asset search (e.g. ["document", "audio", "csv"]).
        When provided, the planner adds type-specific tools (e.g. AUDIO_ANALYSIS for audio assets).

    Returns
    -------
    ExecutionPlan
        The complete execution plan.
    """
    if observer:
        observer.start_tool("planning")

    # 1. Look up base tool list for intent
    base_tools = _INTENT_TOOL_MAP.get(intent, _INTENT_TOOL_MAP["chat"])
    logger.info("[TOOL_PLANNER] Intent=%s base_tools=%d, asset_types=%s",
                intent, len(base_tools), asset_types or "none")

    # 2. Apply context adjustments (now asset-aware + space-aware)
    adjusted_tools = _apply_context_adjustments(
        base_tools,
        intent,
        has_audio_context=has_audio_context,
        has_rag_context=has_rag_context,
        has_knowledge_spaces=has_knowledge_spaces,
        has_agent_memory=has_agent_memory,
        document_type=document_type,
        asset_types=asset_types,
    )

    # 3. Calculate estimated steps (non-optional tools only)
    required_steps = sum(1 for t in adjusted_tools if not t.get("optional", False))
    estimated_steps = max(required_steps, 1)  # At least 1 step

    # 4. Determine render_hint and citation_mode based on intent + tools
    render_hint = _resolve_render_hint(intent, adjusted_tools)
    citation_mode = _resolve_citation_mode(intent, adjusted_tools)

    # 5. Build strategy summary
    strategy_summary = _build_strategy_summary(intent, adjusted_tools)

    plan = ExecutionPlan(
        intent=intent,
        tools=adjusted_tools,
        estimated_steps=estimated_steps,
        render_hint=render_hint,
        citation_mode=citation_mode,
        strategy_summary=strategy_summary,
    )

    if observer:
        observer.finish_tool("planning", plan.to_dict())

    logger.info(
        "[TOOL_PLANNER] Plan created: %d tools, %d steps, render_hint=%s",
        len(adjusted_tools), estimated_steps, render_hint,
    )
    return plan


def _resolve_render_hint(intent: str, tools: list[dict]) -> str:
    """Determine the best render_hint based on intent and selected tools."""
    # Intent → render_hint mapping
    hint_map: dict[str, str] = {
        "executive_summary": "executive_summary",
        "policy_review": "policy_review",
        "frs_analysis": "frs_analysis",
        "meeting_analysis": "meeting_report",
        "risk_assessment": "risk_register",
        "action_extraction": "action_register",
        "workflow_extraction": "workflow_table",
        "process_diagram": "mermaid_diagram",
        "comparison": "comparison_matrix",
        "data_analysis": "chart_viewer",
        "csv_analysis": "chart_viewer",
        "database_analysis": "chart_viewer",
        "report_generation": "report",
        "dashboard_generation": "dashboard",
        "knowledge_discovery": "knowledge_card",
        "audio_analysis": "audio_analysis",
        "document_analysis": "document_analysis",
    }
    hint = hint_map.get(intent)
    if hint:
        return hint

    # Check tools for diagram
    tool_names = [t["tool"].value if isinstance(t["tool"], Enum) else t["tool"] for t in tools]
    if ToolType.DIAGRAM_GENERATION.value in tool_names:
        return "mermaid_diagram"
    if ToolType.CSV_ANALYSIS.value in tool_names or ToolType.DATABASE_QUERY.value in tool_names:
        return "chart_viewer"

    return "narrative"


def _resolve_citation_mode(intent: str, tools: list[dict]) -> str:
    """Determine the citation mode based on intent and tools."""
    if intent in ("executive_summary", "knowledge_discovery"):
        return "summary"
    if intent in ("process_diagram", "dashboard_generation"):
        return "on_demand"
    if intent in ("audio_analysis",):
        return "light"
    if intent in ("action_extraction", "workflow_extraction"):
        return "light"
    return "full"


def _build_strategy_summary(intent: str, tools: list[dict]) -> str:
    """Build a human-readable strategy summary."""
    # Intent descriptions
    descriptions: dict[str, str] = {
        "question_answering": "Direct question answering from knowledge base",
        "executive_summary": "Executive summary generation",
        "document_analysis": "Document intelligence analysis",
        "policy_review": "Policy compliance review",
        "frs_analysis": "Functional requirements analysis",
        "meeting_analysis": "Meeting intelligence report",
        "risk_assessment": "Risk assessment and analysis",
        "action_extraction": "Action item extraction and tracking",
        "workflow_extraction": "Business process workflow extraction",
        "process_diagram": "Process diagram generation",
        "comparison": "Document comparison and gap analysis",
        "root_cause_analysis": "Root cause analysis",
        "data_analysis": "Data analysis and insight generation",
        "csv_analysis": "CSV data analysis",
        "database_analysis": "Database schema and data analysis",
        "report_generation": "Report generation",
        "dashboard_generation": "Dashboard generation",
        "knowledge_discovery": "Knowledge discovery and exploration",
        "image_analysis": "Image analysis",
        "audio_analysis": "Audio recording analysis",
        "chat": "Conversational knowledge retrieval",
    }
    description = descriptions.get(intent, f"Knowledge task: {intent}")
    tool_names = [t["tool"].replace("_", " ").title() for t in tools]
    return f"{description} using {len(tools)} tools: {', '.join(tool_names)}"
