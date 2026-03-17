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

export interface PromptListResponse {
  document_id: string
  prompts: string[]
}

export interface ChatSource {
  chunk_id: string
  snippet: string
}

export interface ChatRequest {
  ec_number?: string | null
  session_id?: string | null
  question: string
  history?: any[] | null
}

export interface ChatResponse {
  document_id: string
  question: string
  answer: string
  sources: ChatSource[]
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

export interface UserHistoryEntry {
  document_id: string
  question: string
  answer: string
}

export interface UserHistoryResponse {
  ec_number: string
  history: UserHistoryEntry[]
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
