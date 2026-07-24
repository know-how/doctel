"""
knowledge_orchestrator_service.py — DocTel Agentic Knowledge Base Orchestration Layer

Determines:
1. What is being asked (intent classification)
2. What knowledge is required (knowledge strategy)
3. What output format is best (output format)
4. How much evidence is needed (citation mode)
5. What structured data to extract (response strategy)
"""
from __future__ import annotations

import re
import logging
from enum import Enum
from typing import Any, Optional

from app.services.tool_planner_service import (
    plan_execution,
    ExecutionPlan,
    ExecutionObserver,
    ToolType,
)
from app.services.tool_execution_service import (
    execute_plan,
    execute_and_build_context,
    EvidenceBundle,
)

logger = logging.getLogger(__name__)


# ── Intent Classification ─────────────────────────────────────────────────────

class KnowledgeIntent(str, Enum):
    QUESTION_ANSWERING = "question_answering"
    EXECUTIVE_SUMMARY = "executive_summary"
    DOCUMENT_ANALYSIS = "document_analysis"
    POLICY_REVIEW = "policy_review"
    FRS_ANALYSIS = "frs_analysis"
    MEETING_ANALYSIS = "meeting_analysis"
    RISK_ASSESSMENT = "risk_assessment"
    ACTION_EXTRACTION = "action_extraction"
    WORKFLOW_EXTRACTION = "workflow_extraction"
    PROCESS_DIAGRAM = "process_diagram"
    COMPARISON = "comparison"
    ROOT_CAUSE_ANALYSIS = "root_cause_analysis"
    DATA_ANALYSIS = "data_analysis"
    CSV_ANALYSIS = "csv_analysis"
    DATABASE_ANALYSIS = "database_analysis"
    REPORT_GENERATION = "report_generation"
    DASHBOARD_GENERATION = "dashboard_generation"
    KNOWLEDGE_DISCOVERY = "knowledge_discovery"
    IMAGE_ANALYSIS = "image_analysis"
    AUDIO_ANALYSIS = "audio_analysis"
    VIDEO_ANALYSIS = "video_analysis"
    CHAT = "chat"


# ── Knowledge Strategy ────────────────────────────────────────────────────────

class KnowledgeStrategy(str, Enum):
    """How knowledge should be sourced for this request."""
    RAG_REQUIRED = "rag_required"           # Must retrieve from vector store
    RAG_OPTIONAL = "rag_optional"           # Retrieve if available, else direct answer
    SESSION_ONLY = "session_only"           # Use only session/audio context
    DATABASE_QUERY = "database_query"       # Query structured database
    CSV_ANALYSIS = "csv_analysis"           # Analyze CSV/tabular data
    LIVE_CONNECTOR = "live_connector"       # Live API/connector query
    MULTI_SOURCE = "multi_source"           # Combine multiple sources
    KNOWLEDGE_GRAPH = "knowledge_graph"     # Traverse knowledge graph
    NONE = "none"                           # Creative/generative only


# ── Output Format ─────────────────────────────────────────────────────────────

class OutputFormat(str, Enum):
    """Best output format for the response."""
    NARRATIVE = "narrative"                     # Free-form text with citations
    EXECUTIVE_SUMMARY = "executive_summary"     # Structured summary card
    ACTION_REGISTER = "action_register"         # Table of action items
    DECISION_REGISTER = "decision_register"     # List of decisions made
    RISK_REGISTER = "risk_register"             # Risk assessment table
    COMPARISON_MATRIX = "comparison_matrix"     # Side-by-side comparison
    WORKFLOW_TABLE = "workflow_table"           # Process step table
    MERMAID_DIAGRAM = "mermaid_diagram"         # Mermaid.js diagram
    TIMELINE = "timeline"                       # Chronological timeline
    CHART = "chart"                             # Data visualization
    MEETING_MINUTES = "meeting_minutes"         # Structured meeting report
    KNOWLEDGE_CARD = "knowledge_card"           # Entity/process knowledge card
    REPORT = "report"                           # Formal report
    DASHBOARD = "dashboard"                     # KPI dashboard


# ── Citation Mode ─────────────────────────────────────────────────────────────

class CitationMode(str, Enum):
    """How citations should be presented."""
    FULL = "full"               # Show all citations with evidence previews
    SUMMARY = "summary"         # Show only document count badge
    LIGHT = "light"             # Show only document names, no sections
    ON_DEMAND = "on_demand"     # Hidden by default, show on user request
    NONE = "none"               # No citations at all


# ── Response Strategy ─────────────────────────────────────────────────────────

class ResponseStrategy:
    """Complete response strategy for a given query."""
    
    def __init__(
        self,
        intent: KnowledgeIntent,
        knowledge_strategy: KnowledgeStrategy,
        output_format: OutputFormat,
        citation_mode: CitationMode,
        render_hint: str,
        system_prompt_override: Optional[str] = None,
        structured_fields: Optional[list[str]] = None,
        confidence: float = 1.0,
        execution_plan: Optional[dict] = None,
    ):
        self.intent = intent
        self.knowledge_strategy = knowledge_strategy
        self.output_format = output_format
        self.citation_mode = citation_mode
        self.render_hint = render_hint
        self.system_prompt_override = system_prompt_override
        self.structured_fields = structured_fields or []
        self.confidence = confidence
        self.execution_plan = execution_plan
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent.value,
            "knowledge_strategy": self.knowledge_strategy.value,
            "output_format": self.output_format.value,
            "citation_mode": self.citation_mode.value,
            "render_hint": self.render_hint,
            "confidence": self.confidence,
        }


# ── Intent Detection (enhanced) ───────────────────────────────────────────────

_INTENT_PATTERNS: dict[KnowledgeIntent, list[str]] = {
    KnowledgeIntent.EXECUTIVE_SUMMARY: [
        r"summarize", r"summary", r"summarise", r"tl;dr", r"gist",
        r"key.?points", r"brief me", r"overview", r"executive.?summary",
        r"high.?level", r"in a nutshell",
    ],
    KnowledgeIntent.POLICY_REVIEW: [
        r"policy", r"compliance", r"regulation", r"governance",
        r"obligation", r"control", r"audit", r"standard",
        r"procedure", r"protocol",
    ],
    KnowledgeIntent.FRS_ANALYSIS: [
        r"frs", r"functional.?requirement", r"business.?rule",
        r"business.?requirement", r"specification",
    ],
    KnowledgeIntent.MEETING_ANALYSIS: [
        r"meeting", r"minutes", r"discussion", r"agenda",
        r"attendee", r"participant", r"workshop", r"session",
    ],
    KnowledgeIntent.RISK_ASSESSMENT: [
        r"risk", r"threat", r"vulnerability", r"hazard",
        r"mitigation", r"control", r"exposure", r"likelihood",
        r"impact", r"severity",
    ],
    KnowledgeIntent.ACTION_EXTRACTION: [
        r"action.?item", r"action", r"task", r"to.?do",
        r"follow.?up", r"owner", r"responsible", r"assignee",
        r"deliverable", r"deadline", r"due.?date",
    ],
    KnowledgeIntent.WORKFLOW_EXTRACTION: [
        r"workflow", r"process", r"flow", r"step", r"procedure",
        r"pipeline", r"lifecycle", r"stage", r"phase",
    ],
    KnowledgeIntent.PROCESS_DIAGRAM: [
        r"diagram", r"flowchart", r"mermaid", r"process.?flow",
        r"architecture", r"schema", r"visualize", r"bpmn",
    ],
    KnowledgeIntent.COMPARISON: [
        r"compare", r"contrast", r"difference", r"vs\.?", r"versus",
        r"similarities", r"pros and cons", r"trade.?off",
    ],
    KnowledgeIntent.ROOT_CAUSE_ANALYSIS: [
        r"root.?cause", r"why did", r"reason for", r"cause",
        r"factor", r"contribute", r"blame", r"failure.?analysis",
    ],
    KnowledgeIntent.DATA_ANALYSIS: [
        r"analyze", r"analyse", r"trend", r"pattern", r"insight",
        r"statistic", r"metric", r"kpi", r"performance",
    ],
    KnowledgeIntent.CSV_ANALYSIS: [
        r"csv", r"spreadsheet", r"excel", r"table", r"tabular",
        r"column", r"row", r"data.?set", r"dataset",
    ],
    KnowledgeIntent.DATABASE_ANALYSIS: [
        r"database", r"sql", r"query", r"schema", r"table",
        r"view", r"index", r"relation", r"entity",
    ],
    KnowledgeIntent.REPORT_GENERATION: [
        r"report", r"generate", r"create", r"draft", r"write",
        r"compose", r"produce", r"document",
    ],
    KnowledgeIntent.DASHBOARD_GENERATION: [
        r"dashboard", r"kpi", r"scorecard", r"overview.?panel",
        r"monitor", r"visualization",
    ],
    KnowledgeIntent.KNOWLEDGE_DISCOVERY: [
        r"what (is|are|does)", r"tell me about", r"explain",
        r"describe", r"define", r"what do we know",
        r"knowledge.?space", r"what space", r"which space",
        r"in what space", r"where is.*stored", r"find.*space",
    ],
    KnowledgeIntent.IMAGE_ANALYSIS: [
        r"image", r"picture", r"photo", r"drawing", r"diagram",
        r"figure", r"illustration", r"visual",
    ],
    KnowledgeIntent.VIDEO_ANALYSIS: [
        r"video", r"video.?recording", r"meeting.?video",
        r"screen.?recording", r"demo.?video", r"training.?video",
        r"watch", r"playback", r"footage", r"frame",
    ],
    KnowledgeIntent.AUDIO_ANALYSIS: [
        r"audio", r"recording", r"transcript", r"recording",
        r"listen", r"playback", r"speaker",
    ],
    KnowledgeIntent.DOCUMENT_ANALYSIS: [
        r"analyze", r"examine", r"evaluate", r"assessment",
        r"review", r"inspect", r"break.?down",
    ],
}


def detect_knowledge_intent(user_query: str) -> KnowledgeIntent:
    """Classify the user query into a KnowledgeIntent.
    
    Uses regex pattern matching against the query text.
    Falls back to CHAT if no intent matches.
    """
    query_lower = user_query.lower()
    
    scored: list[tuple[int, KnowledgeIntent]] = []
    for intent, patterns in _INTENT_PATTERNS.items():
        for pat in patterns:
            match = re.search(pat, query_lower)
            if match:
                # Score by match length (longer matches = more specific)
                score = len(match.group())
                scored.append((score, intent))
                break
    
    if scored:
        scored.sort(key=lambda x: -x[0])
        return scored[0][1]
    
    # If audio context is in session but no specific intent matched,
    # default to meeting analysis for audio content
    return KnowledgeIntent.CHAT


# ── Strategy Resolution ───────────────────────────────────────────────────────

def resolve_strategy(
    intent: KnowledgeIntent,
    has_rag_context: bool = False,
    has_audio_context: bool = False,
    has_knowledge_spaces: bool = False,
    has_agent_memory: bool = False,
    document_type: Optional[str] = None,
    space_asset_types: Optional[list[str]] = None,
) -> ResponseStrategy:
    """Determine the complete response strategy for a given intent and context.

    Steps:
    1. Optionally call discover_by_question() if space_asset_types not provided
       to populate space-aware asset types
    2. Call plan_execution() with space_asset_types + has_knowledge_spaces
    3. Select response strategy based on intent and context

    The execution plan is attached as strategy.execution_plan for observability.

    When ``has_agent_memory`` is True, the execution plan is annotated with
    an ``AGENT_MEMORY`` tool so that downstream code (ask endpoints) can
    invoke ``AgentCoordinator`` before building the final LLM prompt,
    injecting agent findings into context via the plan's execution_metadata.

    Parameters
    ----------
    intent : KnowledgeIntent
        The classified user intent.
    has_rag_context : bool
        Whether vector store retrieval is available.
    has_audio_context : bool
        Whether an audio recording is in session.
    has_knowledge_spaces : bool
        Whether knowledge spaces are available and should be searched.
    has_agent_memory : bool
        Whether the agent memory runtime is available. When True, the
        strategy's execution_plan is annotated with agent_memory_runtime=true
        so that ask endpoints can launch agent coordination before responding.
    document_type : str or None
        Document type classification.
    space_asset_types : list[str] or None
        Asset types discovered via space search. If None, space search
        is skipped (backward compatible).
    """
    # ── Build Tool Execution Plan (space+agent-aware) ──
    _exec_plan = plan_execution(
        intent=intent.value if isinstance(intent, KnowledgeIntent) else intent,
        has_audio_context=has_audio_context,
        has_rag_context=has_rag_context,
        has_knowledge_spaces=has_knowledge_spaces,
        has_agent_memory=has_agent_memory,
        document_type=document_type,
        asset_types=space_asset_types,
    )
    logger.info(
        "[ORCHESTRATOR] Plan: %d tools for intent=%s — %s",
        len(_exec_plan.tools), intent.value if isinstance(intent, KnowledgeIntent) else intent,
        _exec_plan.strategy_summary,
    )
    
    # ── Intent → Strategy Map ──────────────────────────────────────────────
    
    # Executive Summary
    if intent == KnowledgeIntent.EXECUTIVE_SUMMARY:
        return ResponseStrategy(
            intent=intent,
            knowledge_strategy=KnowledgeStrategy.RAG_OPTIONAL,
            output_format=OutputFormat.EXECUTIVE_SUMMARY,
            citation_mode=CitationMode.SUMMARY,
            render_hint="executive_summary",
            structured_fields=["key_findings", "systems", "entities"],
            execution_plan=_exec_plan,)
    
    # Policy Review
    if intent in (KnowledgeIntent.POLICY_REVIEW,):
        return ResponseStrategy(
            intent=intent,
            knowledge_strategy=KnowledgeStrategy.RAG_REQUIRED,
            output_format=OutputFormat.NARRATIVE,
            citation_mode=CitationMode.FULL,
            render_hint="policy_review",
            structured_fields=["obligations", "controls", "risks"],
            execution_plan=_exec_plan,)
    
    # FRS Analysis
    if intent == KnowledgeIntent.FRS_ANALYSIS:
        return ResponseStrategy(
            intent=intent,
            knowledge_strategy=KnowledgeStrategy.RAG_REQUIRED,
            output_format=OutputFormat.NARRATIVE,
            citation_mode=CitationMode.FULL,
            render_hint="frs_analysis",
            structured_fields=["business_rules", "actors", "workflows", "integrations"],
            execution_plan=_exec_plan,)
    
    # Meeting Analysis
    if intent == KnowledgeIntent.MEETING_ANALYSIS or has_audio_context:
        return ResponseStrategy(
            intent=intent,
            knowledge_strategy=KnowledgeStrategy.SESSION_ONLY if has_audio_context else KnowledgeStrategy.RAG_OPTIONAL,
            output_format=OutputFormat.MEETING_MINUTES,
            citation_mode=CitationMode.LIGHT if has_audio_context else CitationMode.FULL,
            render_hint="meeting_report",
            structured_fields=["decisions", "action_items", "risks", "participants", "follow_ups"],
            execution_plan=_exec_plan,)
    
    # Risk Assessment
    if intent == KnowledgeIntent.RISK_ASSESSMENT:
        return ResponseStrategy(
            intent=intent,
            knowledge_strategy=KnowledgeStrategy.RAG_REQUIRED,
            output_format=OutputFormat.RISK_REGISTER,
            citation_mode=CitationMode.FULL,
            render_hint="risk_register",
            structured_fields=["risks", "controls", "severity", "likelihood"],
            execution_plan=_exec_plan,)
    
    # Action Extraction
    if intent == KnowledgeIntent.ACTION_EXTRACTION:
        return ResponseStrategy(
            intent=intent,
            knowledge_strategy=KnowledgeStrategy.RAG_OPTIONAL,
            output_format=OutputFormat.ACTION_REGISTER,
            citation_mode=CitationMode.LIGHT,
            render_hint="action_register",
            structured_fields=["action_items", "owners", "due_dates", "priorities"],
            execution_plan=_exec_plan,)
    
    # Workflow / Process
    if intent in (KnowledgeIntent.WORKFLOW_EXTRACTION,):
        return ResponseStrategy(
            intent=intent,
            knowledge_strategy=KnowledgeStrategy.RAG_REQUIRED,
            output_format=OutputFormat.WORKFLOW_TABLE,
            citation_mode=CitationMode.LIGHT,
            render_hint="workflow_table",
            structured_fields=["steps", "actors", "decisions", "systems"],
            execution_plan=_exec_plan,)
    
    # Process Diagram
    if intent == KnowledgeIntent.PROCESS_DIAGRAM:
        return ResponseStrategy(
            intent=intent,
            knowledge_strategy=KnowledgeStrategy.RAG_OPTIONAL,
            output_format=OutputFormat.MERMAID_DIAGRAM,
            citation_mode=CitationMode.ON_DEMAND,
            render_hint="mermaid_diagram",
            structured_fields=["mermaid_code"],
            execution_plan=_exec_plan,)
    
    # Comparison
    if intent == KnowledgeIntent.COMPARISON:
        return ResponseStrategy(
            intent=intent,
            knowledge_strategy=KnowledgeStrategy.RAG_REQUIRED,
            output_format=OutputFormat.COMPARISON_MATRIX,
            citation_mode=CitationMode.FULL,
            render_hint="comparison_matrix",
            structured_fields=["comparisons", "differences", "similarities"],
            execution_plan=_exec_plan,)
    
    # Root Cause Analysis
    if intent == KnowledgeIntent.ROOT_CAUSE_ANALYSIS:
        return ResponseStrategy(
            intent=intent,
            knowledge_strategy=KnowledgeStrategy.RAG_REQUIRED,
            output_format=OutputFormat.NARRATIVE,
            citation_mode=CitationMode.FULL,
            render_hint="root_cause",
            structured_fields=["causes", "factors", "evidence", "recommendations"],
            execution_plan=_exec_plan,)
    
    # Data / CSV / Database Analysis → Chart / Dashboard
    if intent in (KnowledgeIntent.DATA_ANALYSIS, KnowledgeIntent.CSV_ANALYSIS,
                  KnowledgeIntent.DATABASE_ANALYSIS):
        return ResponseStrategy(
            intent=intent,
            knowledge_strategy=KnowledgeStrategy.RAG_REQUIRED,
            output_format=OutputFormat.CHART,
            citation_mode=CitationMode.ON_DEMAND,
            render_hint="chart_viewer",
            structured_fields=["insights", "trends", "anomalies", "chart_data"],
            execution_plan=_exec_plan,)
    
    # Report Generation
    if intent == KnowledgeIntent.REPORT_GENERATION:
        return ResponseStrategy(
            intent=intent,
            knowledge_strategy=KnowledgeStrategy.RAG_OPTIONAL,
            output_format=OutputFormat.REPORT,
            citation_mode=CitationMode.LIGHT,
            render_hint="report",
            structured_fields=["sections", "findings", "recommendations"],
            execution_plan=_exec_plan,)
    
    # Dashboard Generation
    if intent == KnowledgeIntent.DASHBOARD_GENERATION:
        return ResponseStrategy(
            intent=intent,
            knowledge_strategy=KnowledgeStrategy.RAG_OPTIONAL,
            output_format=OutputFormat.DASHBOARD,
            citation_mode=CitationMode.ON_DEMAND,
            render_hint="dashboard",
            structured_fields=["kpis", "charts", "metrics"],
            execution_plan=_exec_plan,)
    
    # Knowledge Discovery
    if intent == KnowledgeIntent.KNOWLEDGE_DISCOVERY:
        return ResponseStrategy(
            intent=intent,
            knowledge_strategy=KnowledgeStrategy.RAG_OPTIONAL,
            output_format=OutputFormat.KNOWLEDGE_CARD,
            citation_mode=CitationMode.SUMMARY,
            render_hint="knowledge_card",
            structured_fields=["entities", "relationships", "systems", "topics"],
            execution_plan=_exec_plan,)
    
    # Video Analysis
    if intent == KnowledgeIntent.VIDEO_ANALYSIS:
        return ResponseStrategy(
            intent=intent,
            knowledge_strategy=KnowledgeStrategy.SESSION_ONLY,
            output_format=OutputFormat.MEETING_MINUTES,
            citation_mode=CitationMode.LIGHT,
            render_hint="video_analysis",
            structured_fields=["transcript", "visual_events", "slides",
                              "decisions", "action_items", "timeline"],
            execution_plan=_exec_plan,)

    # Audio Analysis
    if intent == KnowledgeIntent.AUDIO_ANALYSIS:
        return ResponseStrategy(
            intent=intent,
            knowledge_strategy=KnowledgeStrategy.SESSION_ONLY,
            output_format=OutputFormat.NARRATIVE,
            citation_mode=CitationMode.LIGHT,
            render_hint="audio_analysis",
            structured_fields=["speakers", "topics", "duration"],
            execution_plan=_exec_plan,)
    
    # Document Analysis
    if intent == KnowledgeIntent.DOCUMENT_ANALYSIS:
        return ResponseStrategy(
            intent=intent,
            knowledge_strategy=KnowledgeStrategy.RAG_REQUIRED,
            output_format=OutputFormat.NARRATIVE,
            citation_mode=CitationMode.FULL,
            render_hint="document_analysis",
            structured_fields=["findings", "entities", "systems", "topics"],
            execution_plan=_exec_plan,)
    
    # Default: question answering
    strategy = ResponseStrategy(
        intent=intent,
        knowledge_strategy=KnowledgeStrategy.RAG_OPTIONAL,
        output_format=OutputFormat.NARRATIVE,
        citation_mode=CitationMode.FULL,
        render_hint="narrative",
        structured_fields=[],
    )
    strategy.execution_plan = _exec_plan
    return strategy


def get_citation_prompt_override(citation_mode: CitationMode) -> str:
    """Get system prompt instructions for the citation mode."""
    instructions = {
        CitationMode.FULL: (
            "For every factual claim, cite the exact source document and section. "
            "Use format: [Source: Document Name, Section N]. "
            "Include the source name inline before each key piece of evidence."
        ),
        CitationMode.SUMMARY: (
            "Provide a flowing narrative summary WITHOUT inline citations. "
            "At the end of your answer, list the sources you used as: "
            "'Sources: Document A, Document B'. "
            "Do NOT reference specific sections or chunks."
        ),
        CitationMode.LIGHT: (
            "Provide your answer naturally. At the end, list the documents "
            "you referenced: 'Sources: Document A, Document B'. "
            "Do NOT use inline section references."
        ),
        CitationMode.ON_DEMAND: (
            "Answer the question directly without citing sources. "
            "The user can request sources separately if needed."
        ),
        CitationMode.NONE: (
            "Answer creatively without citing any sources. "
            "Do not reference any documents."
        ),
    }
    return instructions.get(citation_mode, instructions[CitationMode.FULL])


def get_output_format_prompt(output_format: OutputFormat) -> str:
    """Get system prompt instructions for the output format."""
    instructions = {
        OutputFormat.NARRATIVE: (
            "Write in clear narrative paragraphs. "
            "Organise information logically with a beginning, middle, and conclusion."
        ),
        OutputFormat.EXECUTIVE_SUMMARY: (
            "Provide a concise executive summary with these sections:\n"
            "1. OVERVIEW: 1-2 sentences on purpose and scope\n"
            "2. KEY FINDINGS: Bullet list of most important findings\n"
            "3. SYSTEMS: Key systems and entities mentioned\n"
            "4. CONCLUSION: Business impact or recommended actions"
        ),
        OutputFormat.ACTION_REGISTER: (
            "Extract action items as a table with these columns:\n"
            "| Action | Owner | Due Date | Priority | Status |\n"
            "List all actions found. If owner/due date not specified, mark as 'Not specified'."
        ),
        OutputFormat.DECISION_REGISTER: (
            "List all decisions made as a table:\n"
            "| Decision | Made By | Rationale | Date |\n"
            "Include context for each decision."
        ),
        OutputFormat.RISK_REGISTER: (
            "List all risks as a table:\n"
            "| Risk | Likelihood | Impact | Severity | Mitigation | Owner |\n"
            "Rate likelihood (Low/Medium/High), Impact (Low/Medium/High), "
            "and calculate Severity as a product of both."
        ),
        OutputFormat.COMPARISON_MATRIX: (
            "Create a comparison matrix as a table:\n"
            "| Aspect | Item A | Item B | Notes |\n"
            "Cover all relevant aspects for comparison."
        ),
        OutputFormat.WORKFLOW_TABLE: (
            "Describe the workflow as a table:\n"
            "| Step | Description | Actor | System | Decision | Duration |\n"
            "Include all process steps in order."
        ),
        OutputFormat.MERMAID_DIAGRAM: (
            "Provide a Mermaid.js flowchart that represents the process. "
            "Use ```mermaid ... ``` code block. Then explain the diagram below."
        ),
        OutputFormat.MEETING_MINUTES: (
            "Provide structured meeting minutes with:\n"
            "1. MEETING SUMMARY: Date, topic, participants\n"
            "2. DISCUSSION POINTS: Key discussion items\n"
            "3. DECISIONS: What was decided\n"
            "4. ACTION ITEMS: What needs to be done (| Action | Owner | Due | Priority |)\n"
            "5. RISKS: Any risks identified\n"
            "6. NEXT STEPS: Follow-up actions"
        ),
        OutputFormat.KNOWLEDGE_CARD: (
            "Present the information as a knowledge card with:\n"
            "1. TOPIC: The main subject\n"
            "2. DESCRIPTION: What it is\n"
            "3. RELATED SYSTEMS: Connected systems\n"
            "4. KEY DETAILS: Important facts\n"
            "5. RELATIONSHIPS: How it connects to other entities"
        ),
        OutputFormat.CHART: (
            "Analyze the data and provide:\n"
            "1. KEY INSIGHTS: 2-3 most important findings\n"
            "2. TRENDS: Notable patterns or trends\n"
            "3. ANOMALIES: Any outliers or unusual data points\n"
            "4. Present numeric data in a clear table format."
        ),
        OutputFormat.REPORT: (
            "Generate a formal report with sections:\n"
            "1. EXECUTIVE SUMMARY\n"
            "2. BACKGROUND\n"
            "3. FINDINGS\n"
            "4. ANALYSIS\n"
            "5. RECOMMENDATIONS\n"
            "6. CONCLUSION"
        ),
    }
    return instructions.get(output_format, instructions[OutputFormat.NARRATIVE])


def build_orchestration_prompt(strategy: ResponseStrategy) -> str:
    """Build a complete system prompt section for the orchestration strategy."""
    parts = []
    
    # Output format instructions
    fmt_prompt = get_output_format_prompt(strategy.output_format)
    parts.append(f"[OUTPUT FORMAT: {strategy.output_format.value}]")
    parts.append(fmt_prompt)
    
    # Citation instructions
    cite_prompt = get_citation_prompt_override(strategy.citation_mode)
    parts.append(f"\n[CITATION MODE: {strategy.citation_mode.value}]")
    parts.append(cite_prompt)
    
    # Structured data extraction
    if strategy.structured_fields:
        fields_str = ", ".join(strategy.structured_fields)
        parts.append(f"\n[STRUCTURED DATA]")
        parts.append(f"After your answer, extract structured data for: {fields_str}")
        parts.append(
            "Return the structured data as a JSON block at the end of your response "
            "wrapped in ```json ... ``` tags."
        )
    
    return "\n\n".join(parts)


async def execute_agentic_plan(
    db: Any,
    intent: str,
    user_query: str,
    session_id: Optional[int] = None,
    document_id: Optional[str] = None,
    project_ids: Optional[list[int]] = None,
    audio_transcript: Optional[str] = None,
) -> dict[str, Any]:
    """Execute a multi-agent plan for a given intent and query.

    This is the primary entry point for ask.py endpoints to invoke
    the Agent Runtime. It:
    1. Creates an AgentCoordinator
    2. Initializes it with agent definitions from the DB
    3. Executes the agent plan
    4. Returns the merged AgentEvidenceBundle as a dict

    Usage in ask.py:

        from app.services.knowledge_orchestrator_service import execute_agentic_plan

        agent_bundle = await execute_agentic_plan(
            db=db,
            intent=intent,
            user_query=user_query,
            session_id=session_id,
            audio_transcript=session_state.get("current_transcript"),
        )
        memory_context = agent_bundle.get("execution_summary", "")
        entities = agent_bundle.get("merged_entities", [])

    Parameters
    ----------
    db : AsyncSession
        Database session.
    intent : str
        The detected KnowledgeIntent value.
    user_query : str
        The original user query.
    session_id : int or None
        Session ID for memory scoping.
    document_id : str or None
        Document ID for scoped retrieval.
    project_ids : list[int] or None
        Project IDs for scoped retrieval.
    audio_transcript : str or None
        Audio transcript for media analysis.

    Returns
    -------
    dict
        AgentEvidenceBundle as a dictionary with keys:
        - agent_results: list of agent execution results
        - merged_entities: list of merged entity names
        - merged_actions: list of action items
        - merged_decisions: list of decisions
        - merged_risks: list of risks
        - execution_summary: human-readable summary
        - total_duration_ms: total execution time
    """
    try:
        from app.services.agent_runtime_service import AgentCoordinator

        coordinator = AgentCoordinator(db)
        await coordinator.initialize()
        bundle = await coordinator.execute_agent_plan(
            intent=intent,
            user_query=user_query,
            session_id=session_id,
            document_id=document_id,
            project_ids=project_ids,
            audio_transcript=audio_transcript,
        )
        return bundle.to_dict()
    except Exception as exc:
        logger.warning("[ORCHESTRATOR] execute_agentic_plan failed: %s", exc)
        # Roll back DB transaction to prevent PostgreSQL abort propagation
        try:
            await db.rollback()
        except Exception:
            pass
        return {
            "error": str(exc),
            "agent_results": [],
            "merged_entities": [],
            "execution_summary": f"Agent execution failed: {exc}",
        }


def classify_document_type(doc_analysis: Optional[dict] = None) -> Optional[str]:
    """Classify document type from analysis metadata if available."""
    if not doc_analysis:
        return None
    
    # Check if analysis already has doc_type
    doc_type = doc_analysis.get("doc_type") or doc_analysis.get("classification")
    if doc_type:
        return doc_type
    
    # Infer from filename or entities
    filename = (doc_analysis.get("filename") or "").lower()
    if any(kw in filename for kw in ["policy", "polic", "governance"]):
        return "policy"
    if any(kw in filename for kw in ["frs", "functional", "requirement"]):
        return "frs"
    if any(kw in filename for kw in ["meeting", "minutes", "workshop"]):
        return "meeting"
    if any(kw in filename for kw in ["sop", "procedure", "process"]):
        return "sop"
    if any(kw in filename for kw in ["contract", "agreement", "mou"]):
        return "contract"
    
    return None
