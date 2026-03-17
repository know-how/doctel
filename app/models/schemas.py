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

