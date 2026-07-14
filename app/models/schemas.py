from typing import List, Dict, Any
from pydantic import BaseModel, Field


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


class ModelLabelsResponse(BaseModel):
    """Model display labels"""
    labels: Dict[str, str] = Field(default_factory=dict)

