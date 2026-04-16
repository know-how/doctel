import {
  DocumentCreateResponse,
  DocumentAnalysisResponse,
  PromptListResponse,
  ChatRequest,
  ChatResponse,
  ProjectCreateRequest,
  ProjectResponse,
  ProjectListResponse,
  LoginRequest,
  LoginResponse,
  EmailOtpRequest,
  EmailOtpVerifyRequest,
  EmailOtpRequestResponse,
  SummaryHistoryResponse,
  IngestStatusResponse,
  ChatSessionCreateResponse,
  ChatMessagesResponse,
  ModelsAvailableResponse,
  ModelPullStatusResponse,
  BootstrapStatusResponse,
  MyProjectsResponse,
  MyDocumentsResponse,
  ChatSessionsListResponse,
  UserMeResponse,
  AdminSettingsResponse,
  AdminSettingsPatchResponse,
  AdminSettingsAuditResponse,
} from "../types/api"

const BASE_URL =
  (import.meta as any).env.VITE_API_BASE_URL ?? "http://localhost:8000"
const AUTH_TOKEN_KEY = "docintel_auth_token"

export class ApiError extends Error {
  status: number
  data: any
  constructor(message: string, status: number, data: any) {
    super(message)
    this.status = status
    this.data = data
  }
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    if (res.status === 401) {
      clearAuthToken()
      window.dispatchEvent(new CustomEvent("docintel_logout"))
      throw new ApiError("Session expired. Please sign in again.", 401, { error: "token_expired" })
    }
    const text = await res.text().catch(() => "")
    try {
      const parsed = JSON.parse(text)
      if (res.status === 403) {
        const detail = parsed?.detail ?? parsed?.message ?? ""
        const err = parsed?.error ?? ""
        const msg = String(detail || err || "").toLowerCase()
        if (msg.includes("access to project denied")) {
          throw new ApiError(
            "You don’t have access to this project. Please request access or contact the admin.",
            403,
            parsed,
          )
        }
      }
      const msg = parsed?.message ?? parsed?.detail?.message ?? null
      const err = parsed?.error ?? parsed?.detail?.error ?? parsed?.detail ?? null
      const pull = parsed?.pull_command ?? parsed?.detail?.pull_command ?? null
      if (typeof msg === "string" && msg.trim()) {
        throw new ApiError(pull ? `${msg} Pull with: ${pull}` : msg, res.status, parsed)
      }
      if (typeof err === "string" && err.trim()) throw new ApiError(err, res.status, parsed)
      throw new ApiError(text || res.statusText, res.status, parsed)
    } catch (error) {
      if (error instanceof ApiError) {
        throw error
      }
      throw new ApiError(text || res.statusText, res.status, null)
    }
  }
  return (await res.json()) as T
}

async function handleBlobResponse(res: Response): Promise<Blob> {
  if (!res.ok) {
    if (res.status === 401) {
      clearAuthToken()
      window.dispatchEvent(new CustomEvent("docintel_logout"))
      throw new ApiError("Session expired. Please sign in again.", 401, { error: "token_expired" })
    }
    const text = await res.text().catch(() => "")
    throw new ApiError(text || res.statusText, res.status, null)
  }
  return await res.blob()
}

function getAuthToken(): string | null {
  if (typeof window === "undefined") return null
  return window.localStorage.getItem(AUTH_TOKEN_KEY)
}

export function setAuthToken(token: string) {
  if (typeof window === "undefined") return
  window.localStorage.setItem(AUTH_TOKEN_KEY, token)
  window.dispatchEvent(new CustomEvent("docintel_auth_changed"))
}

export function clearAuthToken() {
  if (typeof window === "undefined") return
  window.localStorage.removeItem(AUTH_TOKEN_KEY)
  window.dispatchEvent(new CustomEvent("docintel_auth_changed"))
}

function buildAuthHeaders(): Record<string, string> {
  const token = getAuthToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export async function login(payload: LoginRequest): Promise<LoginResponse> {
  const res = await fetch(`${BASE_URL}/auth/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  })
  return handleResponse<LoginResponse>(res)
}

export async function logout(): Promise<{ success: boolean }> {
  const res = await fetch(`${BASE_URL}/auth/logout`, {
    method: "POST",
    headers: buildAuthHeaders(),
  })
  return handleResponse<{ success: boolean }>(res)
}

export async function getMe(): Promise<UserMeResponse> {
  const res = await fetch(`${BASE_URL}/users/me`, {
    headers: buildAuthHeaders(),
  })
  return handleResponse<UserMeResponse>(res)
}

export async function getUiSettings(): Promise<any> {
  const res = await fetch(`${BASE_URL}/api/settings/ui`, {
    headers: buildAuthHeaders(),
  })
  return handleResponse<any>(res)
}

export async function adminGetSettings(): Promise<AdminSettingsResponse> {
  const res = await fetch(`${BASE_URL}/admin/settings`, {
    headers: buildAuthHeaders(),
  })
  return handleResponse<AdminSettingsResponse>(res)
}

export async function adminPatchSettings(payload: any): Promise<AdminSettingsPatchResponse> {
  const res = await fetch(`${BASE_URL}/admin/settings`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      ...buildAuthHeaders(),
    },
    body: JSON.stringify(payload ?? {}),
  })
  return handleResponse<AdminSettingsPatchResponse>(res)
}

export async function adminTestSettings(payload: any): Promise<{ ok: boolean; restart_recommended: Record<string, boolean> }> {
  const res = await fetch(`${BASE_URL}/admin/settings/test`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...buildAuthHeaders(),
    },
    body: JSON.stringify(payload ?? {}),
  })
  return handleResponse<{ ok: boolean; restart_recommended: Record<string, boolean> }>(res)
}

export async function adminBackupSettings(): Promise<{ ok: boolean; path: string }> {
  const res = await fetch(`${BASE_URL}/admin/settings/backup`, {
    method: "POST",
    headers: buildAuthHeaders(),
  })
  return handleResponse<{ ok: boolean; path: string }>(res)
}

export async function adminGetSettingsAudit(limit: number = 100, key?: string): Promise<AdminSettingsAuditResponse> {
  const url = key
    ? `${BASE_URL}/admin/settings/audit?limit=${encodeURIComponent(String(limit))}&key=${encodeURIComponent(
        key,
      )}`
    : `${BASE_URL}/admin/settings/audit?limit=${encodeURIComponent(String(limit))}`
  const res = await fetch(url, {
    headers: buildAuthHeaders(),
  })
  return handleResponse<AdminSettingsAuditResponse>(res)
}

export async function requestEmailOtp(
  payload: EmailOtpRequest,
): Promise<EmailOtpRequestResponse> {
  const res = await fetch(`${BASE_URL}/auth/email/request`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  })
  return handleResponse<EmailOtpRequestResponse>(res)
}

export async function verifyEmailOtp(
  payload: EmailOtpVerifyRequest,
): Promise<LoginResponse> {
  const res = await fetch(`${BASE_URL}/auth/email/verify`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  })
  return handleResponse<LoginResponse>(res)
}

export async function uploadDocument(
  file: File,
  metadata?: {
    project_id?: string | null
    project_name?: string | null
    document_type?: string | null
    document_date?: string | null
  },
): Promise<DocumentCreateResponse> {
  const formData = new FormData()
  formData.append("file", file)
  if (metadata?.project_id) {
    formData.append("project_id", metadata.project_id)
  }
  if (metadata?.project_name) {
    formData.append("project_name", metadata.project_name)
  }
  if (metadata?.document_type) {
    formData.append("document_type", metadata.document_type)
  }
  if (metadata?.document_date) {
    formData.append("document_date", metadata.document_date)
  }

  const res = await fetch(`${BASE_URL}/documents`, {
    method: "POST",
    headers: buildAuthHeaders(),
    body: formData,
  })
  return handleResponse<DocumentCreateResponse>(res)
}

export async function getDocumentAnalysis(
  documentId: string,
): Promise<DocumentAnalysisResponse> {
  const res = await fetch(`${BASE_URL}/documents/${documentId}/analysis`, {
    headers: buildAuthHeaders(),
  })
  return handleResponse<DocumentAnalysisResponse>(res)
}

export async function getProjectAnalysis(
  projectId: string,
): Promise<DocumentAnalysisResponse> {
  const res = await fetch(`${BASE_URL}/projects/${projectId}/analysis`, {
    headers: buildAuthHeaders(),
  })
  return handleResponse<DocumentAnalysisResponse>(res)
}

export async function getDocumentPrompts(
  documentId: string,
): Promise<PromptListResponse> {
  const res = await fetch(`${BASE_URL}/documents/${documentId}/prompts`, {
    headers: buildAuthHeaders(),
  })
  return handleResponse<PromptListResponse>(res)
}

export async function suggestPrompts(
  documentId: string,
): Promise<{ prompts: string[]; groups?: any[]; scope?: string }> {
  const res = await fetch(
    `${BASE_URL}/api/prompts/suggest?document_id=${encodeURIComponent(documentId)}`,
    { headers: buildAuthHeaders() },
  )
  return handleResponse<{ prompts: string[]; groups?: any[]; scope?: string }>(res)
}

export async function flowchartGenerate(payload: { text: string; diagram_type?: string; model?: string }) {
  const res = await fetch(`${BASE_URL}/api/flowchart/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...buildAuthHeaders() },
    body: JSON.stringify(payload),
  })
  return handleResponse<{ mermaid: string; drawing_prompt: string }>(res)
}

export async function chartsAnalyze(file: File) {
  const form = new FormData()
  form.append("file", file)
  const res = await fetch(`${BASE_URL}/api/charts/analyze`, {
    method: "POST",
    headers: buildAuthHeaders(),
    body: form,
  })
  return handleResponse<{ columns: string[]; numeric_columns: string[]; suggestions: any[] }>(res)
}

export async function chartsBuild(payload: {
  session_id: string
  chart_type: string
  title?: string
  x: string
  y: string[]
  data: any[]
}) {
  const res = await fetch(`${BASE_URL}/api/charts/build`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...buildAuthHeaders() },
    body: JSON.stringify(payload),
  })
  return handleResponse<{ ok: boolean; url: string }>(res)
}

export async function downloadDocumentFile(documentId: string): Promise<Blob> {
  const res = await fetch(`${BASE_URL}/documents/${documentId}/file`, {
    headers: buildAuthHeaders(),
  })
  return handleBlobResponse(res)
}

export async function chatWithDocument(
  documentId: string,
  payload: ChatRequest,
): Promise<ChatResponse> {
  const res = await fetch(`${BASE_URL}/api/ask/${documentId}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...buildAuthHeaders(),
    },
    body: JSON.stringify(payload),
  })
  return handleResponse<ChatResponse>(res)
}

export async function chatGlobally(payload: ChatRequest): Promise<ChatResponse> {
  const res = await fetch(`${BASE_URL}/api/ask`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...buildAuthHeaders(),
    },
    body: JSON.stringify(payload),
  })
  return handleResponse<ChatResponse>(res)
}

export async function createChatSession(
  documentId?: string | null,
  scope?: "global" | "project" | "document",
): Promise<ChatSessionCreateResponse> {
  const body: Record<string, any> = {}
  if (documentId) body.document_id = documentId
  if (scope) body.scope = scope
  const res = await fetch(`${BASE_URL}/api/chat/sessions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...buildAuthHeaders(),
    },
    body: JSON.stringify(body),
  })
  return handleResponse<ChatSessionCreateResponse>(res)
}

export async function getChatMessages(
  sessionId: string,
  limit: number = 100,
): Promise<ChatMessagesResponse> {
  const res = await fetch(
    `${BASE_URL}/api/chat/sessions/${encodeURIComponent(sessionId)}/messages?limit=${encodeURIComponent(
      String(limit),
    )}`,
    {
      headers: buildAuthHeaders(),
    },
  )
  return handleResponse<ChatMessagesResponse>(res)
}

export async function getAvailableModels(): Promise<ModelsAvailableResponse> {
  const res = await fetch(`${BASE_URL}/api/models/available`, {
    headers: buildAuthHeaders(),
  })
  return handleResponse<ModelsAvailableResponse>(res)
}

export async function setChatSessionModel(
  sessionId: string,
  model: string,
): Promise<{ ok: boolean; session_id: string; model: string }> {
  const res = await fetch(`${BASE_URL}/api/chat/sessions/${encodeURIComponent(sessionId)}/model`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...buildAuthHeaders(),
    },
    body: JSON.stringify({ model }),
  })
  return handleResponse<{ ok: boolean; session_id: string; model: string }>(res)
}

export async function startModelPull(
  model: string,
  resume: boolean = true,
): Promise<ModelPullStatusResponse> {
  const res = await fetch(`${BASE_URL}/api/models/pull`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...buildAuthHeaders(),
    },
    body: JSON.stringify({ model, resume }),
  })
  return handleResponse<ModelPullStatusResponse>(res)
}

export async function getModelPullStatus(model: string): Promise<ModelPullStatusResponse> {
  const res = await fetch(`${BASE_URL}/api/models/pull/status/${encodeURIComponent(model)}`, {
    headers: buildAuthHeaders(),
  })
  return handleResponse<ModelPullStatusResponse>(res)
}

export async function getBootstrapStatus(): Promise<BootstrapStatusResponse> {
  const res = await fetch(`${BASE_URL}/api/bootstrap/status`, {
    headers: buildAuthHeaders(),
  })
  return handleResponse<BootstrapStatusResponse>(res)
}

export async function getMyProjects(): Promise<MyProjectsResponse> {
  const res = await fetch(`${BASE_URL}/api/me/projects`, {
    headers: buildAuthHeaders(),
  })
  return handleResponse<MyProjectsResponse>(res)
}

export async function getMyDocuments(): Promise<MyDocumentsResponse> {
  const res = await fetch(`${BASE_URL}/api/me/documents`, {
    headers: buildAuthHeaders(),
  })
  return handleResponse<MyDocumentsResponse>(res)
}

export async function downloadDocumentFileApi(documentId: string): Promise<Blob> {
  const res = await fetch(`${BASE_URL}/api/documents/${encodeURIComponent(documentId)}/download`, {
    headers: buildAuthHeaders(),
  })
  return handleBlobResponse(res)
}

export async function listChatSessions(projectId?: string, limit: number = 50): Promise<ChatSessionsListResponse> {
  const base = projectId
    ? `${BASE_URL}/api/chat/sessions?project_id=${encodeURIComponent(projectId)}`
    : `${BASE_URL}/api/chat/sessions`
  const url = `${base}${base.includes("?") ? "&" : "?"}limit=${encodeURIComponent(String(limit))}`
  const res = await fetch(url, { headers: buildAuthHeaders() })
  return handleResponse<ChatSessionsListResponse>(res)
}

export async function getSummaryHistory(): Promise<SummaryHistoryResponse> {
  const res = await fetch(`${BASE_URL}/users/me/summary-history`, {
    headers: buildAuthHeaders(),
  })
  return handleResponse<SummaryHistoryResponse>(res)
}

export async function getIngestStatus(
  documentId: string,
): Promise<IngestStatusResponse> {
  const res = await fetch(
    `${BASE_URL}/api/ingest/status?document_id=${encodeURIComponent(documentId)}`,
    {
      headers: buildAuthHeaders(),
    },
  )
  return handleResponse<IngestStatusResponse>(res)
}

export async function retryIngest(documentId: string): Promise<{ ok: boolean }> {
  const res = await fetch(`${BASE_URL}/api/ingest/retry`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...buildAuthHeaders(),
    },
    body: JSON.stringify({ document_id: documentId }),
  })
  return handleResponse<{ ok: boolean }>(res)
}

export async function createProject(
  payload: ProjectCreateRequest,
): Promise<ProjectResponse> {
  const res = await fetch(`${BASE_URL}/projects`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...buildAuthHeaders(),
    },
    body: JSON.stringify(payload),
  })
  return handleResponse<ProjectResponse>(res)
}

export async function getProjects(): Promise<ProjectListResponse> {
  const res = await fetch(`${BASE_URL}/projects`, {
    headers: buildAuthHeaders(),
  })
  return handleResponse<ProjectListResponse>(res)
}
