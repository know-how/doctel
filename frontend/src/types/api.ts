export interface DocumentMetadata {
  project_id?: string | null
  project_name?: string | null
  document_type?: string | null
  document_date?: string | null
}

export interface DocumentCreateResponse {
  id: string
  filename: string
  status: string
  metadata?: DocumentMetadata | null
}

export interface DocumentAnalysisResponse {
  id: string
  executive_summary: string
  detailed_summary: string[]
  entities: string[]
  key_entities?: Record<string, string[]>
  topics: string[]
  sentiment: string
  action_items?: string[]
  decisions?: string[]
  status: string
}

export interface PromptListResponse {
  document_id: string
  prompts: string[]
}

export interface ProjectCreateRequest {
  name: string
}

export interface ProjectSummary {
  id: string
  name: string
  document_count: number
}

export interface ProjectResponse {
  id: string
  name: string
  document_ids: string[]
}

export interface ProjectListResponse {
  projects: ProjectSummary[]
}

export interface ProjectDocumentListResponse {
  project_id: string
  document_ids: string[]
}

export interface ChatRequest {
  question: string
  project_id?: number
  session_id?: string
  pending_message_id?: number | string
  model?: string
  scope?: "project" | "all"
  force_policy?: boolean
  force_diagram?: boolean
}

export interface ChatAskOkResponse {
  answer: string
  citations: { filename: string; chunk_index: number; text: string }[]
  cross_references?: { filename: string; reason: string }[]
  used_model: string
  session_id: string
}

export interface ChatAskQueuedResponse {
  status: "queued" | "pending_analysis"
  reason: string
  document_status: string
  retry_after_ms: number
  poll_url: string
  session_id: string
  pending_message_id?: number
}

export type ChatResponse = ChatAskOkResponse | ChatAskQueuedResponse

export interface ChatSessionCreateResponse {
  session_id: string
}

export interface ChatMessage {
  id: number
  role: "user" | "assistant" | "system"
  content: string
  status: "pending" | "done" | "failed"
  citations: { filename: string; chunk_index: number; text: string }[]
  created_at: string
}

export interface ChatMessagesResponse {
  session_id: string
  messages: ChatMessage[]
}

export interface ModelsAvailableResponse {
  installed?: string[]
  available?: string[]
  models?: string[]
  default_model?: string
  offline?: boolean
  embed_model?: string
  vision_model?: string
}

export interface ModelPullStatusResponse {
  model: string
  state: "idle" | "pending" | "downloading" | "verifying" | "retrying" | "success" | "failed"
  percent: number
  bytes_completed: number
  bytes_total: number
  eta_seconds?: number | null
  attempt: number
  last_event: string
  error?: string
  resume_supported?: boolean
  installed?: boolean
}

export interface BootstrapStatusResponse {
  running: boolean
  scanned: number
  new: number
  updated: number
  skipped: number
  percent: number
  last_error?: string
}

export interface MyProjectsResponse {
  projects: { id: string; name: string; role: string }[]
}

export interface MyDocumentsResponse {
  documents: {
    id: string
    filename: string
    project_id: string | null
    project_name: string
    status: string
    created_at: string
    download_url: string
    view_url: string
    needs_project_review?: boolean
    auto_project_confidence?: number
  }[]
}

export interface ChatSessionsListResponse {
  sessions: {
    session_id: string
    title?: string
    scope?: string
    project_id: string | null
    document_id?: string | null
    model: string
    started_at: string
    updated_at?: string
  }[]
}

export interface LoginRequest {
  ec_number: string
  password: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
  ec_number: string
  display_name?: string | null
  role?: string
  email?: string
  user_id?: number
}

export interface UserMeResponse {
  username: string
  role: string
  user_id?: number
  ec_number?: string
  email?: string
  display_name?: string
}

export interface AdminSettingsResponse {
  effective: any
  sources: Record<string, "default" | "file" | "db">
}

export interface AdminSettingsPatchResponse {
  ok: boolean
  restart_recommended: Record<string, boolean>
  effective: any
  sources: Record<string, "default" | "file" | "db">
}

export interface AdminSettingsAuditResponse {
  audit: {
    id: number
    key: string
    old_value: string
    new_value: string
    changed_by_user_id: number
    changed_at: string
  }[]
}

export interface EmailOtpRequest {
  email: string
}

export interface EmailOtpVerifyRequest {
  email: string
  code: string
}

export interface EmailOtpRequestResponse {
  message: string
}

export interface SummaryHistoryEntry {
  document_id: string
  executive_summary: string
  detailed_summary: string[]
  topics: string[]
  entities: string[]
  key_entities?: Record<string, string[]>
  sentiment: string
  action_items?: string[]
  decisions?: string[]
  created_at: string
}

export interface SummaryHistoryResponse {
  ec_number: string
  history: SummaryHistoryEntry[]
}

export interface IngestStatusResponse {
  document_id?: number
  status: string
  step: string
  percent: number
  message: string
  error_message?: string
  analysis_ready?: boolean
  ingestion_started?: boolean
  ingestion_completed?: boolean
  ingestion_failed?: boolean
  updated_at: string
}
