from typing import List, Dict, Any
from pydantic import BaseModel, Field, BeforeValidator
from typing_extensions import Annotated


# ── Defensive type: accept int OR str for fields that may come from DB (int) or API (str) ──
# Pydantic v2 strict mode rejects int for str | None fields, causing ValidationError.
# This validator converts int → str at the boundary so callers don't have to.
def _coerce_str(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return str(v)
    return v

CoercibleStr = Annotated[str | None, BeforeValidator(_coerce_str)]


class DocumentMetadata(BaseModel):
    project_id: str | None = None
    project_name: str | None = None
    document_type: str | None = None
    document_date: str | None = None


class DocumentCreateResponse(BaseModel):
    id: str
    filename: str
    status: str = Field(description="Processing status of the document")
    metadata: DocumentMetadata | None = None


class DocumentAnalysisResponse(BaseModel):
    id: str
    executive_summary: str
    detailed_summary: List[str]
    entities: List[str]
    key_entities: Dict[str, List[str]] = Field(default_factory=dict)
    topics: List[str]
    sentiment: str
    action_items: List[str] = Field(default_factory=list)
    decisions: List[str] = Field(default_factory=list)
    status: str


class PromptListResponse(BaseModel):
    document_id: str
    prompts: List[str]


class ProjectCreateRequest(BaseModel):
    name: str


class ProjectSummary(BaseModel):
    id: str
    name: str
    document_count: int


class ProjectResponse(BaseModel):
    id: str
    name: str
    document_ids: List[str]


class ProjectListResponse(BaseModel):
    projects: List[ProjectSummary]


class ProjectDocumentListResponse(BaseModel):
    project_id: str
    document_ids: List[str]


class ChatRequest(BaseModel):
    ec_number: str | None = None
    session_id: str | None = None
    question: str
    history: List[Dict[str, Any]] | None = None
    selected_model: str | None = None


class ChatSource(BaseModel):
    chunk_id: str
    snippet: str


class ChatResponse(BaseModel):
    document_id: str
    question: str
    answer: str
    sources: List[ChatSource]


class LoginRequest(BaseModel):
    ec_number: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    ec_number: str
    display_name: str | None = None


class EmailOtpRequest(BaseModel):
    email: str


class EmailOtpVerifyRequest(BaseModel):
    email: str
    code: str


class EmailOtpRequestResponse(BaseModel):
    message: str


class SummaryHistoryEntry(BaseModel):
    document_id: str
    executive_summary: str
    detailed_summary: List[str]
    topics: List[str]
    entities: List[str]
    key_entities: Dict[str, List[str]] = Field(default_factory=dict)
    sentiment: str
    action_items: List[str] = Field(default_factory=list)
    decisions: List[str] = Field(default_factory=list)
    created_at: str


class SummaryHistoryResponse(BaseModel):
    ec_number: str
    history: List[SummaryHistoryEntry]


# Ask Response Models
class Citation(BaseModel):
    """Citation source for answer with full chunk text"""
    document_id: str | None = None
    filename: str | None = None
    chunk_index: int | None = None
    text: str | None = None  # Full chunk text excerpt
    snippet: str | None = None  # Backward compatibility alias
    page: int | None = None
    full_text_available: bool | None = None
    distance: float | None = None  # Relevance score (lower is better)

    # ── Enterprise permission & action URLs ────────────────────────────────
    # These are Optional[bool] (rather than plain bool) because enrich_citations
    # may return citations without these fields when a citation has no document_id.
    # Pydantic v2 rejects None for plain bool fields even when a default is set.
    can_view: bool | None = None
    can_download: bool | None = None
    open_url: str | None = None
    download_url: str | None = None
    preview_url: str | None = None
    source_type: str | None = None
    project_id: CoercibleStr = None


class CrossReference(BaseModel):
    """Cross reference to a document"""
    filename: str
    reason: str = "Used as retrieval context"


class AskResponse(BaseModel):
    """Response from ask endpoints"""
    answer: str
    reasoning: str | None = None
    citations: List[Citation] = Field(default_factory=list)
    cross_references: List[CrossReference] = Field(default_factory=list)
    used_model: str | None = None
    session_id: str | None = None

    # ── Orchestration fields ──────────────────────────────────────────────
    render_hint: str | None = Field(
        default=None,
        description="Frontend rendering hint: narrative, executive_summary, meeting_report, action_register, risk_register, comparison_matrix, workflow_table, mermaid_diagram, chart_viewer, knowledge_card, report",
    )
    citation_mode: str | None = Field(
        default=None,
        description="Citation display mode: full, summary, light, on_demand, none",
    )
    structured_data: Dict[str, Any] | None = Field(
        default=None,
        description="Structured data extracted from the answer (action_items, decisions, risks, etc.)",
    )
    knowledge_type: str | None = Field(
        default=None,
        description="Knowledge source type: document, audio, csv, database, session, none",
    )
    confidence: float | None = Field(
        default=None,
        description="Confidence score for the answer (0.0 to 1.0)",
    )
    evidence_count: int | None = Field(
        default=None,
        description="Number of evidence chunks used to generate the answer",
    )
    source_count: int | None = Field(
        default=None,
        description="Number of unique sources cited",
    )
    execution_plan: dict[str, Any] | None = Field(
        default=None,
        description="Tool execution plan from the Tool Planning Layer",
    )


class UploadedDocument(BaseModel):
    """Uploaded document info"""
    id: str
    filename: str
    status: str
    detected_type: str | None = None
    is_public: bool = False


class UploadResponse(BaseModel):
    """Response from document upload"""
    documents: List[UploadedDocument]


class ProjectInfo(BaseModel):
    """Basic project information"""
    id: str
    name: str
    document_count: int = 0
    created_at: str = ""
    updated_at: str = ""
    last_activity: str = ""


class ProjectsListResponse(BaseModel):
    """Response for projects list"""
    projects: List[ProjectInfo]


class BasicResponse(BaseModel):
    """Simple ok/error response"""
    ok: bool
    error: str | None = None


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    reason: str | None = None
    message: str | None = None


class OllamaModelDetail(BaseModel):
    """Detail about an Ollama model"""
    name: str
    size: int = 0
    size_human: str = ""
    family: str = ""
    parameter_size: str = ""
    quantization_level: str = ""
    modified_at: str = ""
    digest: str = ""
    ready: bool = False
    capabilities: List[str] = Field(default_factory=list, description="Modality capability flags: text, vision, audio, code, reasoning, embedding, fast, large")
    display_category: str = ""
    # Cloud/API model metadata (not used by Ollama but present for cloud models)
    vision: bool = False
    tool_calling: bool = False
    max_input_tokens: int = 128000
    max_output_tokens: int = 16000


class ModelsAvailableResponse(BaseModel):
    """Available models response"""
    installed: List[str]
    available: List[str]
    offline: bool = False
    default_model: str | None = None
    embed_model: str | None = None
    vision_model: str | None = None
    models: List[OllamaModelDetail] = Field(default_factory=list)
    ollama_healthy: bool = True
    defaults: Dict[str, str] = Field(default_factory=dict)
    v2_providers: List[dict] = Field(default_factory=list)
    v2_auto_routing: bool = True


class ModelLabelsResponse(BaseModel):
    """Model display labels"""
    labels: Dict[str, str] = Field(default_factory=dict)

