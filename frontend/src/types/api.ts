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
  is_public?: boolean
  metadata?: DocumentMetadata | null
}

/** Enterprise summary — structured business intelligence sections per document type. */
export interface EnterpriseSummary {
  doc_type: "policy" | "frs" | "meeting" | "sop" | "generic"
  executive_summary: string
  key_findings: string[]
  responsibilities?: { role: string; department: string; responsibility: string }[]
  risks?: { risk: string; mitigation: string }[]
  actions?: string[]
  business_impact?: string
  systems_entities?: { name: string; type: string }[]
  // Policy-specific
  objectives?: string[]
  scope?: string
  compliance_requirements?: string[]
  // FRS-specific
  business_overview?: string
  functional_requirements?: string[]
  integrations?: { system: string; integration_type: string; description: string }[]
  actors?: string[]
  workflows?: { name: string; steps: string[]; actors_involved: string[] }[]
  business_rules?: string[]
  // Meeting-specific
  meeting_purpose?: string
  participants?: string[]
  topics_discussed?: string[]
  decisions?: string[]
  action_items?: { owner: string; action: string; due_date: string }[]
  next_steps?: string[]
  // SOP-specific
  purpose?: string
  process_steps?: { step_number: number; step: string; responsible: string }[]
  controls?: string[]
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

export interface Citation {
  filename: string
  chunk_index: number
  text: string
  full_text_available?: boolean
  distance?: number
  /** Enterprise permission / action fields – present on enriched responses */
  can_view?: boolean
  can_download?: boolean
  open_url?: string
  download_url?: string
  preview_url?: string
  source_type?: string
  project_id?: string | number
}

export interface ChatAskOkResponse {
  answer: string
  citations: Citation[]
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
  reasoning?: string
  status: "pending" | "done" | "failed"
  citations: Citation[]
  created_at: string
}

export interface ChatMessagesResponse {
  session_id: string
  messages: ChatMessage[]
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
  // Cloud/API model metadata (present when size_human === "Cloud")
  vision?: boolean
  tool_calling?: boolean
  max_input_tokens?: number
  max_output_tokens?: number
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
  defaults?: Record<string, string>
  v2_providers?: V2Provider[]
  v2_auto_routing?: boolean
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
    is_public?: boolean
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
  total: number
  page: number
  page_size: number
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

/* ───── Model Registry types ───── */

export interface RegistryModelEntry {
  id: string
  name: string
  vision?: boolean
  toolCalling?: boolean
  context_window?: number
  capabilities?: string[]
}

export interface RegistryProvider {
  id: string
  name: string
  vendor?: string
  base_url?: string
  models: RegistryModelEntry[]
}

export interface RegistryListResponse {
  providers: RegistryProvider[]
}

export interface RegistryFlatModel {
  id: string
  name: string
  provider_id: string
  provider_name: string
  vendor?: string
  vision?: boolean
  toolCalling?: boolean
  context_window?: number
  capabilities?: string[]
}

export interface RegistryFlatResponse {
  models: RegistryFlatModel[]
}

export interface RegistryProviderResponse {
  provider: RegistryProvider
}

export interface RegistryModelResponse {
  model: RegistryModelEntry
}

export interface AddRegistryProviderPayload {
  name: string
  vendor?: string
  base_url?: string
  models?: Partial<RegistryModelEntry>[]
}

export interface UpdateRegistryProviderPayload {
  name?: string
  vendor?: string
  base_url?: string
}

export interface AddRegistryModelPayload {
  id: string
  name: string
  vision?: boolean
  toolCalling?: boolean
  context_window?: number
  capabilities?: string[]
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
  dev_code?: string
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

/* ───── Model Management v2 Types (GitHub Copilot-style) ───── */

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
  state: string  // active | inactive | installed | available | maintenance | retired | downloading | error
  isDefault: boolean
  allowedRoles: string[]
  departmentRestrictions: string[]
  pricingTier: string
  license: string
  forTasks?: string[]
  capabilities?: string[]
  health?: V2HealthSummary
  // Status-driven availability (computed from state)
  isSelectable?: boolean  // true when state in ['active', 'installed', 'available']
  isVisible?: boolean     // true when state in ['active', 'installed', 'available', 'maintenance']
  // Visibility control
  visibleToUsers?: boolean  // admin toggle for user-facing visibility
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
  // Provider endpoint configuration
  providerType?: string
  modelsEndpoint?: string
  chatEndpoint?: string
  messagesEndpoint?: string
  embeddingsEndpoint?: string
  healthEndpoint?: string
  // Visibility control
  visibleToUsers?: boolean  // admin toggle for user-facing visibility
}

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

// ── Test Connection ──

export interface V2TestConnectionRequest {
  baseUrl?: string
  apiKey?: string
  model?: string
  providerId?: string
}

export interface V2TestConnectionResponse {
  success: boolean
  latencyMs?: number
  statusCode?: number
  message?: string
}

// ── Fetch Models ──

export interface V2FetchModelsRequest {
  baseUrl?: string
  apiKey?: string
  providerId?: string
}

export interface V2FetchModelsResponse {
  success: boolean
  latencyMs?: number
  models?: { id: string; name?: string; owned_by?: string }[]
  count?: number
  statusCode?: number
  message?: string
  providerId?: string
  // Full synchronization results
  added?: number
  updated?: number
  removed?: number
  unchanged?: number
  preserved?: number
}

// ── Embedding Governance ──

export interface EmbeddingStatusResponse {
  total_documents: number
  embedded: number
  pending: number
  version_mismatch: number
  provider_model_mismatch: number
  configured_provider: string | null
  configured_model: string | null
  embedding_version: string
}

export interface EmbeddingMismatchItem {
  id: number
  filename: string
  project_id: number | null
  current_provider: string | null
  current_model: string | null
  current_version: string | null
  embedded_at: string | null
  needs_reembed: boolean
}

export interface EmbeddingMismatchesResponse {
  documents: EmbeddingMismatchItem[]
  total: number
  configured: {
    provider: string
    model: string
    version: string
  } | null
}

export interface ReembedSingleResponse {
  success: boolean
  doc_id?: number
  chunks_reembedded?: number
  provider?: string
  model?: string
  dimensions?: number
  error?: string
}

export interface ReembedBulkResponse {
  success: boolean
  reembedded: number[]
  errors: { doc_id: number; error: string }[]
  total: number
}
