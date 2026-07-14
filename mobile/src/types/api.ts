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
  project_name?: string
  filename?: string
  document_type?: string
  document_date?: string
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

export interface OllamaModelDetail {
  name: string
  size: number
  size_human: string
  family: string
  parameter_size: string
  quantization_level: string
  modified_at: string
  digest: string
  ready: boolean
  capabilities?: string[]
  display_category?: string
}

export interface ModelsAvailableResponse {
  installed?: string[]
  available?: string[]
  models?: OllamaModelDetail[]
  default_model?: string
  offline?: boolean
  embed_model?: string
  vision_model?: string
  ollama_healthy?: boolean
  v2_providers?: V2Provider[]
  v2_auto_routing?: boolean
}

/* ══════════════════════════════════════════════════════════════════════════════
   Model Management v2 Types
   ══════════════════════════════════════════════════════════════════════════════ */

export interface V2HealthSummary {
  label: string
  status: "healthy" | "degraded" | "unhealthy" | "unknown"
  totalRequests: number
  successCount: number
  errorCount: number
  successRate: number
  avgLatencyMs: number | null
  p95LatencyMs: number | null
  totalTokens: number
  lastChecked: string | null
  recentErrors: { timestamp: string; latency_ms?: number }[]
}

export interface V2ModelMetadata {
  id: string
  name: string
  contextWindow: number
  supportsChat: boolean
  supportsVision: boolean
  supportsTools: boolean
  supportsCode: boolean
  supportsEmbedding: boolean
  supportsReasoning: boolean
  supportsRag: boolean
  supportsClassification: boolean
  supportsSummary: boolean
  supportsExtraction: boolean
  enabled: boolean
  visibleToUsers: boolean
  isDefault: boolean
  allowedRoles: string[]
  departmentRestrictions: string[]
  state: string
  pricingTier: string
  license: string
  forTasks?: string[]
  capabilities?: string[]
  health?: V2HealthSummary
}

export interface V2Provider {
  id: string
  name: string
  vendor: string
  base_url: string
  api_key_value: string
  status: string
  description: string
  icon: string
  order: number
  models: V2ModelMetadata[]
  health?: V2HealthSummary
}

export interface V2CatalogResponse {
  providers: V2Provider[]
  taskMapping: Record<string, { providerId: string; modelId: string; modelName?: string; providerName?: string }>
  automaticRouting: boolean
  taskTypes: string[]
  validRoles: string[]
  validDepartments: string[]
  validCapabilities: string[]
  automaticRoutingRules: Record<string, { description: string; priority_capabilities: string[]; preferred_family: string | null }>
  marketplace: V2MarketplaceItem[]
}

export interface V2MarketplaceItem {
  modelId: string
  modelName: string
  providerId: string
  providerName: string
  contextWindow: number
  capabilities: string[]
  pricingTier: string
  license: string
  state: string
}

export interface V2ProviderListResponse {
  providers: V2Provider[]
}

export interface V2ProviderResponse {
  provider: V2Provider
}

export interface V2ModelListResponse {
  models: V2ModelMetadata[]
}

export interface V2ModelResponse {
  model: V2ModelMetadata
}

export interface V2TaskMappingResponse {
  taskMapping: Record<string, { providerId: string; modelId: string }>
  taskTypes: string[]
}

export interface V2VisibleChatModelsResponse {
  models: (V2ModelMetadata & { provider_name: string; provider_id: string })[]
}

export interface V2HealthResponse {
  providers: Record<string, V2HealthSummary>
  models: Record<string, V2HealthSummary>
  system: V2HealthSummary
}

export interface V2AuditEntry {
  id: string
  timestamp: string
  action: string
  entityType: string
  entityId: string
  details: Record<string, any>
  userId: string
  userName: string
}

export interface V2AuditResponse {
  audit: V2AuditEntry[]
  total: number
}

export interface V2RoutingStatusResponse {
  automaticRouting: boolean
}

export interface V2ReferenceResponse {
  taskTypes: string[]
  validRoles: string[]
  validDepartments: string[]
  modelStates: string[]
}

export interface V2RoutingSelectResponse {
  model: V2ModelMetadata & { provider_id: string; provider_name?: string; selection?: string; reason?: string }
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

export interface MyDocument {
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
}

export interface MyDocumentsResponse {
  documents: MyDocument[]
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

export interface IngestStatusResponse {
  status: string
  percent: number
  message: string
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
  settings: Record<string, any>
  sources: Record<string, string>
}

export interface AdminSettingsPatchResponse {
  ok: boolean
  applied: Record<string, any>
  restart_recommended: boolean
}

export interface AdminSettingsAuditResponse {
  audit: Array<{
    key: string
    old_value: any
    new_value: any
    changed_by: string
    changed_at: string
  }>
}
