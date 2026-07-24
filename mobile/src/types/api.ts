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

export interface Citation {
  document_id?: string | null
  filename?: string
  chunk_index?: number
  text?: string
  snippet?: string
  full_text_available?: boolean
  distance?: number
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
  reasoning?: string
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
  defaults?: Record<string, string>
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

/* ══════════════════════════════════════════════════════════════════════════════
   Knowledge Asset Types (P0 mobile-web parity)
   ══════════════════════════════════════════════════════════════════════════════ */

export interface KnowledgeAsset {
  id: string
  asset_type: "document" | "audio" | "video" | "csv" | "image" | "database"
  title: string
  description?: string
  tags?: string[]
  entities?: string[]
  topics?: string[]
  metadata?: Record<string, any>
  workspace_id?: string
  repository_id?: string
  source_uri?: string
  created_at?: string
  updated_at?: string
}

export interface KnowledgeAssetRelationship {
  id?: string
  source_asset_id: string
  target_asset_id: string
  type: string
  metadata?: Record<string, any>
  created_at?: string
}

export interface KnowledgeAssetListResponse {
  assets: KnowledgeAsset[]
  total: number
  limit: number
  offset: number
}

export interface KnowledgeAssetRelatedResponse {
  related: KnowledgeAsset[]
  total: number
}

export interface KnowledgeAssetStatsResponse {
  counts: Record<string, number>
  total: number
}

/* ══════════════════════════════════════════════════════════════════════════════
   Knowledge Space Types (P0 mobile-web parity)
   ══════════════════════════════════════════════════════════════════════════════ */

export interface KnowledgeSpace {
  space_id: string
  name: string
  description?: string
  department?: string
  tags?: string[]
  owner_id?: string
  is_active?: boolean
  created_at?: string
  updated_at?: string
}

export interface KnowledgeSpaceListResponse {
  spaces: KnowledgeSpace[]
  total: number
}

export interface KnowledgeSpaceAssetsResponse {
  assets: KnowledgeAsset[]
  total: number
}

export interface KnowledgeSpaceInsightsResponse {
  space_id: string
  name: string
  asset_counts: Record<string, number>
  recent_assets: KnowledgeAsset[]
  related_spaces: KnowledgeSpace[]
  media_breakdown: Record<string, number>
}

export interface KnowledgeSpaceRelatedResponse {
  related: KnowledgeSpace[]
  total: number
}

/* ══════════════════════════════════════════════════════════════════════════════
   Knowledge Graph Types (P0 mobile-web parity)
   ══════════════════════════════════════════════════════════════════════════════ */

export interface GraphNode {
  id: string
  node_id: string
  node_type: string
  label: string
  description?: string
  metadata?: Record<string, any>
  importance?: number
  source_document_id?: string
  is_active?: boolean
  created_at?: string
}

export interface GraphEdge {
  id: number
  source_node_id: number
  target_node_id: number
  relation: string
  weight?: number
  source_document_id?: string
  metadata?: Record<string, any>
  created_at?: string
}

export interface GraphNodeListResponse {
  nodes: GraphNode[]
  total: number
}

export interface GraphEdgeListResponse {
  edges: GraphEdge[]
  total: number
}

export interface GraphDiscoverByEntityResponse {
  entity: string
  related_entities: any[]
  related_assets: KnowledgeAsset[]
  total_entities: number
  total_assets: number
}

export interface GraphPathResponse {
  paths: { nodes: GraphNode[]; edges: GraphEdge[] }[]
  total_paths: number
}

export interface GraphExploreResponse {
  nodes: GraphNode[]
  edges: GraphEdge[]
  total_nodes: number
  total_edges_shown: number
}

export interface GraphStatsResponse {
  total_nodes: number
  total_edges: number
  node_type_counts: Record<string, number>
  edge_type_counts: Record<string, number>
}

/* ══════════════════════════════════════════════════════════════════════════════
   Agent Runtime Types (P0 mobile-web parity)
   ══════════════════════════════════════════════════════════════════════════════ */

export interface AgentInfo {
  agent_type: string
  name?: string
  description?: string
  purpose?: string
  tools?: string[]
}

export interface AgentResult {
  agent_type: string
  status: string
  duration_ms: number
  summary?: string
  key_findings?: string[]
  entities_count?: number
  actions_count?: number
  decisions_count?: number
  risks_count?: number
  has_evidence?: boolean
  error?: string
}

export interface AgentExecutionBundle {
  agents_executed: number
  agent_results: AgentResult[]
  execution_summary?: string
  merged_entities?: string[]
  merged_actions?: any[]
  merged_decisions?: any[]
  merged_risks?: any[]
  total_duration_ms?: number
}

export interface AgentExecuteResponse {
  execution_summary?: string
  entities?: string[]
  actions?: any[]
  decisions?: any[]
  risks?: any[]
  agent_results?: AgentResult[]
  total_duration_ms?: number
}

export interface AgentMemoryEntry {
  id: number
  agent_execution_id: number
  session_id?: number
  memory_type: string
  key: string
  value: any
  created_at?: string
}

export interface AgentMemoryContextResponse {
  session_id: number
  context: string
  context_length: number
}

/* ══════════════════════════════════════════════════════════════════════════════
   Workflow Engine Types (P0 mobile-web parity)
   ══════════════════════════════════════════════════════════════════════════════ */

export interface WorkflowDefinition {
  workflow_type: string
  name: string
  description: string
  agent_count: number
  expected_deliverables: string[]
  success_criteria: string[]
}

export interface WorkflowStep {
  step_id: number
  agent_type: string
  purpose: string
  status: string
  result?: Record<string, any>
  duration_ms?: number
  error?: string
}

export interface WorkflowExecution {
  execution_id: string
  workflow_type: string
  objective: string
  status: string
  steps: WorkflowStep[]
  deliverables?: Record<string, any>
  merged_entities?: string[]
  merged_actions_count?: number
  merged_decisions_count?: number
  merged_risks_count?: number
  execution_summary?: string
  error?: string
  started_at?: string
  completed_at?: string
  total_duration_ms?: number
}

export interface WorkflowExecuteResponse extends WorkflowExecution {}

export interface WorkflowListResponse {
  workflows: WorkflowDefinition[]
}

/* ══════════════════════════════════════════════════════════════════════════════
   Chat / Streaming Types (P0 mobile-web parity)
   ══════════════════════════════════════════════════════════════════════════════ */

export interface ToolPlanTool {
  tool: string
  purpose: string
  optional: boolean
}

export interface ExecutionMetadata {
  tools_executed?: string[]
  completed?: number
  failed?: number
  total_time_sec?: number
  results?: Record<string, { elapsed_sec: number; status: string; error?: string }>
  errors?: Record<string, string>
}

export interface ExecutionPlan {
  intent: string
  tools: ToolPlanTool[]
  estimated_steps: number
  render_hint: string
  citation_mode: string
  strategy_summary: string
  execution_metadata?: ExecutionMetadata
  agent_execution?: AgentExecutionBundle
}

export interface DocumentStreamCallbacks {
  onChunk: (chunk: string, model: string, sessionId: string) => void
  onReasoning?: (reasoning: string, model: string, sessionId: string) => void
  onCitations?: (citations: any[]) => void
  onMetadata?: (metadata: Record<string, any>) => void
  onDone: (fullText: string, model: string, sessionId: string) => void
  onError: (error: string) => void
}

/* ══════════════════════════════════════════════════════════════════════════════
   Audio Context Types (P0 mobile-web parity)
   ══════════════════════════════════════════════════════════════════════════════ */

export interface AudioContextData {
  filename: string
  transcript: string
  summary?: string
  durationSec?: number | null
  entities?: string[]
  topics?: string[]
  speakerCount?: number
}

export interface MeetingAnalysis {
  summary: string
  participants: string[]
  topics: string[]
  decisions: { decision: string; made_by?: string }[]
  action_items: { action: string; owner?: string; priority?: string; due_date?: string }[]
  risks: { risk: string; severity?: string }[]
  follow_ups: string[]
  key_dates: string[]
  systems_mentioned: string[]
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
