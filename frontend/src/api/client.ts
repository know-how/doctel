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
  RegistryListResponse,
  RegistryFlatResponse,
  RegistryProviderResponse,
  RegistryModelResponse,
  AddRegistryProviderPayload,
  UpdateRegistryProviderPayload,
  AddRegistryModelPayload,
  V2CatalogResponse,
  V2ProviderListResponse,
  V2ProviderResponse,
  V2ModelListResponse,
  V2ModelResponse,
  V2TaskMappingResponse,
  V2VisibleChatModelsResponse,
  V2HealthResponse,
  V2AuditResponse,
  V2RoutingStatusResponse,
  V2ReferenceResponse,
} from "../types/api"

function getApiBaseUrl(): string {
  const raw = (import.meta as any).env.VITE_API_BASE_URL
  if (typeof raw === "string" && raw.trim()) return raw.trim().replace(/\/+$/, "")
  return ""
}

const BASE_URL = getApiBaseUrl()
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
    const text = await res.text().catch(() => "")
    try {
      const parsed = JSON.parse(text)
      if (res.status === 401) {
        const detail = parsed?.detail
        const err = parsed?.error ?? (typeof detail === 'object' ? detail?.error : null) ?? (typeof detail === 'string' ? detail : null) ?? null
        const isTokenExpired = err === "token_expired" || (typeof detail === 'string' && detail === "token_expired")
        if (isTokenExpired) {
          clearAuthToken()
          window.dispatchEvent(new CustomEvent("docintel_logout"))
          throw new ApiError("Session expired. Please sign in again.", 401, { error: "token_expired" })
        }
        const msg = parsed?.message ?? (typeof detail === 'object' ? detail?.message : null) ?? (typeof detail === 'string' ? detail : null) ?? null
        if (typeof msg === "string" && msg.trim()) {
          throw new ApiError(msg, res.status, parsed)
        }
        if (typeof err === "string" && err.trim()) throw new ApiError(err, res.status, parsed)
        throw new ApiError(text || res.statusText, res.status, parsed)
      }
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
      const detail = parsed?.detail
      const detailStr = typeof detail === 'string' ? detail : null
      const msg = parsed?.message ?? (typeof detail === 'object' ? detail?.message : null) ?? detailStr ?? null
      const err = parsed?.error ?? (typeof detail === 'object' ? detail?.error : null) ?? (typeof detail === 'string' ? detail : null) ?? null
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
      const text = await res.text().catch(() => "")
      let isTokenExpired = false
      try {
        const parsed = JSON.parse(text)
        const err = parsed?.error
        const detail = parsed?.detail
        isTokenExpired = err === "token_expired" || detail === "token_expired"
      } catch {}
      if (isTokenExpired) {
        clearAuthToken()
        window.dispatchEvent(new CustomEvent("docintel_logout"))
        throw new ApiError("Session expired. Please sign in again.", 401, { error: "token_expired" })
      }
      throw new ApiError(text || res.statusText, res.status, null)
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

/**
 * Check whether the backend is reachable by calling the public /healthz endpoint.
 * Does NOT require authentication. Returns the connection status and any error.
 * Uses simple fetch without AbortController to avoid ERR_ABORTED issues.
 */
export async function checkBackendConnection(
  timeoutMs = 5_000,
): Promise<{ ok: boolean; error?: string; details?: any }> {
  try {
    const res = await fetch(`${BASE_URL}/healthz`, {
      method: "GET",
    })
    if (!res.ok) {
      return { ok: false, error: `Server returned ${res.status}` }
    }
    return { ok: true }
  } catch (err: any) {
    return { ok: false, error: err?.message ?? "Unable to reach server." }
  }
}

/**
 * Detailed health check that diagnoses specific service issues.
 * Uses proven existing endpoints: /healthz (backend) and /api/health/ollama (Ollama).
 * This avoids relying on a new complex endpoint that might have issues.
 */
export async function checkDetailedHealth(
  timeoutMs = 8_000,
): Promise<{
  ok: boolean
  error?: string
  backendRunning: boolean
  ollamaRunning: boolean
  ollamaError?: string
  hasExternalServices: boolean
}> {
  // Step 1: Check if backend is running using the proven /healthz endpoint
  let backendRunning = false
  try {
    const res = await fetch(`${BASE_URL}/healthz`, { method: "GET" })
    backendRunning = res.ok
  } catch {
    backendRunning = false
  }

  if (!backendRunning) {
    return {
      ok: false,
      error: "Backend server is not running. Start the server with 'python -m uvicorn app.main:app --host 127.0.0.1 --port 8000' and retry.",
      backendRunning: false,
      ollamaRunning: false,
      hasExternalServices: false,
    }
  }

  // Step 2: Backend is running — check Ollama status using the existing /api/health/ollama endpoint
  let ollamaRunning = false
  let ollamaError: string | undefined
  try {
    const res = await fetch(`${BASE_URL}/api/health/ollama`, { method: "GET" })
    if (res.ok) {
      const data = await res.json()
      ollamaRunning = data?.ok ?? false
      if (!ollamaRunning && data?.hint) {
        ollamaError = data.hint
      }
    } else {
      ollamaRunning = false
    }
  } catch {
    ollamaRunning = false
  }

  // Step 3: Check if any external services are configured via /api/models/available
  let hasExternalServices = false
  try {
    const res = await fetch(`${BASE_URL}/api/models/available`, { method: "GET" })
    if (res.ok) {
      const data = await res.json()
      const models = data?.models || []
      hasExternalServices = models.some((m: any) =>
        m?.size_human === "Cloud" || m?.name?.startsWith("gemini") || m?.name?.startsWith("deepseek") || m?.name?.startsWith("go/") || m?.name?.startsWith("zen/") || m?.name?.startsWith("huggingface/")
      )
    }
  } catch {
    hasExternalServices = false
  }

  // If Ollama is down but external services are available, the app is still usable
  if (!ollamaRunning && hasExternalServices) {
    return {
      ok: true,
      backendRunning: true,
      ollamaRunning: false,
      ollamaError,
      hasExternalServices,
    }
  }

  if (!ollamaRunning) {
    return {
      ok: false,
      error: ollamaError ?? "Local AI models (Ollama) are not running. Start Ollama with 'ollama serve' and retry.",
      backendRunning: true,
      ollamaRunning: false,
      ollamaError,
      hasExternalServices,
    }
  }

  return {
    ok: true,
    backendRunning: true,
    ollamaRunning: true,
    hasExternalServices,
  }
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
    is_public?: boolean
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
  formData.append("is_public", metadata?.is_public ? "true" : "false")

  const res = await fetch(`${BASE_URL}/documents`, {
    method: "POST",
    headers: buildAuthHeaders(),
    body: formData,
  })
  return handleResponse<DocumentCreateResponse>(res)
}

/**
 * Upload a document with XMLHttpRequest-based progress tracking.
 * @param onProgress - callback receiving a number 0-100 for upload percentage
 */
export async function uploadDocumentWithProgress(
  file: File,
  onProgress?: (percent: number) => void,
  metadata?: {
    project_id?: string | null
    project_name?: string | null
    document_type?: string | null
    document_date?: string | null
    is_public?: boolean
  },
): Promise<DocumentCreateResponse> {
  return new Promise((resolve, reject) => {
    const formData = new FormData()
    formData.append("file", file)
    if (metadata?.project_id) formData.append("project_id", metadata.project_id)
    if (metadata?.project_name) formData.append("project_name", metadata.project_name)
    if (metadata?.document_type) formData.append("document_type", metadata.document_type)
    if (metadata?.document_date) formData.append("document_date", metadata.document_date)
    formData.append("is_public", metadata?.is_public ? "true" : "false")

    const xhr = new XMLHttpRequest()
    xhr.open("POST", `${BASE_URL}/documents`)

    // Copy auth headers
    const token = localStorage.getItem(AUTH_TOKEN_KEY)
    if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`)

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) {
        const pct = Math.round((e.loaded / e.total) * 100)
        onProgress(pct)
      }
    }

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText))
        } catch {
          reject(new Error("Invalid response from server"))
        }
      } else {
        try {
          const data = JSON.parse(xhr.responseText)
          reject(new ApiError(data.detail || data.message || "Upload failed", xhr.status, data))
        } catch {
          reject(new ApiError("Upload failed", xhr.status, {}))
        }
      }
    }

    xhr.onerror = () => reject(new Error("Network error during upload"))
    xhr.ontimeout = () => reject(new Error("Upload timed out"))
    xhr.send(formData)
  })
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

export interface StreamCallbacks {
  onChunk: (chunk: string, model: string, sessionId: string) => void
  onDone: (fullText: string, model: string, sessionId: string) => void
  onError: (error: string) => void
}

async function consumeSSEStream(response: Response, callbacks: StreamCallbacks, timeoutMs: number = 120_000): Promise<void> {
  const reader = response.body?.getReader()
  if (!reader) {
    callbacks.onError("No response body")
    return
  }
  const decoder = new TextDecoder()
  let buffer = ""
  let fullText = ""
  let model = ""
  let sessionId = ""
  let timedOut = false

  const timeoutId = setTimeout(() => {
    timedOut = true
    reader.cancel()
    callbacks.onError("The AI model did not respond within 2 minutes. Please try again.")
  }, timeoutMs)

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      if (timedOut) return
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split("\n")
      buffer = lines.pop() || ""

      for (const line of lines) {
        const trimmed = line.trim()
        if (!trimmed.startsWith("data: ")) continue
        const payload = trimmed.slice(6).trim()
        if (payload === "[DONE]") {
          clearTimeout(timeoutId)
          callbacks.onDone(fullText, model, sessionId)
          return
        }
        try {
          const data = JSON.parse(payload)
          if (data.error) {
            clearTimeout(timeoutId)
            callbacks.onError(data.error)
            return
          }
          if (data.chunk) {
            fullText += data.chunk
            model = data.model || model
            sessionId = data.session_id || sessionId
            callbacks.onChunk(data.chunk, model, sessionId)
          }
        } catch {
          // skip malformed JSON
        }
      }
    }
  } catch (err: any) {
    if (!timedOut) {
      clearTimeout(timeoutId)
      callbacks.onError(err?.message ?? "Stream read error")
    }
    return
  }
  clearTimeout(timeoutId)
  callbacks.onDone(fullText, model, sessionId)
}

export async function chatWithDocumentStream(
  documentId: string,
  payload: ChatRequest,
  callbacks: StreamCallbacks,
): Promise<void> {
  const res = await fetch(`${BASE_URL}/api/ask/${documentId}/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...buildAuthHeaders(),
    },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    try {
      const err = await res.json()
      callbacks.onError(err.error || err.message || `HTTP ${res.status}`)
    } catch {
      callbacks.onError(`HTTP ${res.status}`)
    }
    return
  }
  return consumeSSEStream(res, callbacks)
}

export async function chatGloballyStream(
  payload: ChatRequest,
  callbacks: StreamCallbacks,
): Promise<void> {
  const res = await fetch(`${BASE_URL}/api/ask/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...buildAuthHeaders(),
    },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    try {
      const err = await res.json()
      callbacks.onError(err.error || err.message || `HTTP ${res.status}`)
    } catch {
      callbacks.onError(`HTTP ${res.status}`)
    }
    return
  }
  return consumeSSEStream(res, callbacks)
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

export async function getModelCapabilities(): Promise<{
  capabilities: Record<string, string[]>
  labels: Record<string, string>
}> {
  const res = await fetch(`${BASE_URL}/api/models/capabilities`, {
    headers: buildAuthHeaders(),
  })
  return handleResponse<{
    capabilities: Record<string, string[]>
    labels: Record<string, string>
  }>(res)
}

export async function getSingleModelCapabilities(
  modelId: string,
): Promise<{
  model_id: string
  capabilities: string[]
  display_category: string
}> {
  const res = await fetch(
    `${BASE_URL}/api/models/${encodeURIComponent(modelId)}/capabilities`,
    { headers: buildAuthHeaders() },
  )
  return handleResponse<{
    model_id: string
    capabilities: string[]
    display_category: string
  }>(res)
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

export async function getMyDocuments(page?: number, pageSize?: number): Promise<any> {
  const params = new URLSearchParams()
  if (page != null) params.set("page", String(page))
  if (pageSize != null) params.set("page_size", String(pageSize))
  const qs = params.toString()
  const url = qs ? `${BASE_URL}/api/me/documents?${qs}` : `${BASE_URL}/api/me/documents`
  const res = await fetch(url, { headers: buildAuthHeaders() })
  return handleResponse<any>(res)
}

export async function deleteDocument(documentId: string): Promise<{ ok: boolean }> {
  const res = await fetch(`${BASE_URL}/api/documents/${encodeURIComponent(documentId)}`, {
    method: "DELETE",
    headers: buildAuthHeaders(),
  })
  return handleResponse<{ ok: boolean }>(res)
}

export async function updateProject(projectId: string, payload: { name?: string }): Promise<any> {
  const res = await fetch(`${BASE_URL}/api/projects/${encodeURIComponent(projectId)}`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      ...buildAuthHeaders(),
    },
    body: JSON.stringify(payload),
  })
  return handleResponse<any>(res)
}

export async function deleteProject(projectId: string): Promise<{ ok: boolean }> {
  const res = await fetch(`${BASE_URL}/api/projects/${encodeURIComponent(projectId)}`, {
    method: "DELETE",
    headers: buildAuthHeaders(),
  })
  return handleResponse<{ ok: boolean }>(res)
}

export async function overrideDocumentProjectAPI(documentId: string, projectId: string): Promise<{ ok: boolean }> {
  const res = await fetch(`${BASE_URL}/api/documents/${encodeURIComponent(documentId)}/project`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      ...buildAuthHeaders(),
    },
    body: JSON.stringify({ project_id: projectId }),
  })
  return handleResponse<{ ok: boolean }>(res)
}

export async function downloadDocumentFileApi(documentId: string): Promise<Blob> {
  const res = await fetch(`${BASE_URL}/api/documents/${encodeURIComponent(documentId)}/download`, {
    headers: buildAuthHeaders(),
  })
  return handleBlobResponse(res)
}

export async function listChatSessions(projectId?: string, limit: number = 50, page?: number): Promise<ChatSessionsListResponse> {
  const params = new URLSearchParams()
  if (projectId) params.set("project_id", encodeURIComponent(projectId))
  if (limit) params.set("limit", String(limit))
  if (page) params.set("page", String(page))
  const qs = params.toString()
  const url = qs ? `${BASE_URL}/api/chat/sessions?${qs}` : `${BASE_URL}/api/chat/sessions`
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
  const res = await fetch(`${BASE_URL}/api/projects`, {
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

export async function getModelLabels(): Promise<{ labels: Record<string, string> }> {
  const res = await fetch(`${BASE_URL}/api/models/labels`, {
    headers: buildAuthHeaders(),
  })
  return handleResponse<{ labels: Record<string, string> }>(res)
}

// ── Theme ──────────────────────────────────────────

export async function saveUserThemePreference(theme: string): Promise<any> {
  const res = await fetch(`${BASE_URL}/api/settings/ui`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...buildAuthHeaders(),
    },
    body: JSON.stringify({ theme }),
  })
  return handleResponse<any>(res)
}

// ── Documents ──────────────────────────────────────

export async function getDocumentLibrary(
  filters?: {
    search?: string
    project_id?: string
    status?: string
    tag?: string
    visibility?: string
    page?: number
    page_size?: number
  },
): Promise<any> {
  const params = new URLSearchParams()
  if (filters?.search) params.set("search", filters.search)
  if (filters?.project_id) params.set("project_id", filters.project_id)
  if (filters?.status) params.set("status", filters.status)
  if (filters?.tag) params.set("tag", filters.tag)
  if (filters?.visibility) params.set("visibility", filters.visibility)
  if (filters?.page != null) params.set("page", String(filters.page))
  if (filters?.page_size != null) params.set("page_size", String(filters.page_size))
  const qs = params.toString()
  const url = qs ? `${BASE_URL}/api/documents?${qs}` : `${BASE_URL}/api/documents`
  const res = await fetch(url, { headers: buildAuthHeaders() })
  return handleResponse<any>(res)
}

export async function getWorkspaces(): Promise<any> {
  const res = await fetch(`${BASE_URL}/api/projects`, {
    headers: buildAuthHeaders(),
  })
  return handleResponse<any>(res)
}

export async function getProcessingStatus(documentId: string): Promise<any> {
  const res = await fetch(
    `${BASE_URL}/api/ingest/${encodeURIComponent(documentId)}/status`,
    { headers: buildAuthHeaders() },
  )
  return handleResponse<any>(res)
}

// ── Analyze ────────────────────────────────────────

export async function runExtraction(
  schema: string,
  documentIds: string[],
): Promise<any> {
  const res = await fetch(`${BASE_URL}/api/analyze/extraction`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...buildAuthHeaders(),
    },
    body: JSON.stringify({ schema, document_ids: documentIds }),
  })
  return handleResponse<any>(res)
}

export async function generateSummary(documentIds: string[]): Promise<any> {
  const res = await fetch(`${BASE_URL}/api/analyze/summaries`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...buildAuthHeaders(),
    },
    body: JSON.stringify({ document_ids: documentIds }),
  })
  return handleResponse<any>(res)
}

export async function classifyDocuments(payload: { rules: string; document_ids?: string[]; model?: string }): Promise<any> {
  const res = await fetch(`${BASE_URL}/api/analyze/classification`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...buildAuthHeaders(),
    },
    body: JSON.stringify(payload),
  })
  return handleResponse<any>(res)
}

export async function compareDocuments(docA: string, docB: string): Promise<any> {
  const res = await fetch(`${BASE_URL}/api/analyze/compare`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...buildAuthHeaders(),
    },
    body: JSON.stringify({ doc_a: docA, doc_b: docB }),
  })
  return handleResponse<any>(res)
}

// ── Outputs ────────────────────────────────────────

export async function getOutputs(
  filters?: { type?: string; page?: number; page_size?: number },
): Promise<any> {
  const params = new URLSearchParams()
  if (filters?.type) params.set("type", filters.type)
  if (filters?.page != null) params.set("page", String(filters.page))
  if (filters?.page_size != null) params.set("page_size", String(filters.page_size))
  const qs = params.toString()
  const url = qs ? `${BASE_URL}/api/outputs?${qs}` : `${BASE_URL}/api/outputs`
  const res = await fetch(url, { headers: buildAuthHeaders() })
  return handleResponse<any>(res)
}

export async function exportOutput(
  outputId: string,
  format: string,
): Promise<Blob> {
  const res = await fetch(
    `${BASE_URL}/api/outputs/${encodeURIComponent(outputId)}/export?format=${encodeURIComponent(format)}`,
    { headers: buildAuthHeaders() },
  )
  return handleBlobResponse(res)
}

// ── Admin Models ───────────────────────────────────

export async function setDefaultModel(
  taskType: string,
  modelId: string,
): Promise<any> {
  const res = await fetch(`${BASE_URL}/admin/models/default`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...buildAuthHeaders(),
    },
    body: JSON.stringify({ task_type: taskType, model_id: modelId }),
  })
  return handleResponse<any>(res)
}

/** Update integration settings (API keys, base URLs, etc.). */
export async function adminSetIntegrations(payload: Record<string, string>): Promise<{ ok: boolean; updated: Record<string, string> }> {
  const res = await fetch(`${BASE_URL}/admin/integrations`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      ...buildAuthHeaders(),
    },
    body: JSON.stringify(payload),
  })
  return handleResponse<{ ok: boolean; updated: Record<string, string> }>(res)
}

export async function savePrompt(
  promptType: string,
  content: string,
): Promise<any> {
  const res = await fetch(`${BASE_URL}/admin/prompts`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...buildAuthHeaders(),
    },
    body: JSON.stringify({ prompt_type: promptType, content }),
  })
  return handleResponse<any>(res)
}

export async function getPrompts(): Promise<any> {
  const res = await fetch(`${BASE_URL}/admin/prompts`, {
    headers: buildAuthHeaders(),
  })
  return handleResponse<any>(res)
}

export async function updateIntegrationSettings(config: object): Promise<any> {
  const res = await fetch(`${BASE_URL}/admin/integrations`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      ...buildAuthHeaders(),
    },
    body: JSON.stringify(config),
  })
  return handleResponse<any>(res)
}

// ── Collaboration ──────────────────────────────────

export async function getTeamMembers(): Promise<any> {
  const res = await fetch(`${BASE_URL}/api/team`, {
    headers: buildAuthHeaders(),
  })
  return handleResponse<any>(res)
}

export async function updateMemberRole(
  userId: number,
  role: string,
): Promise<any> {
  const res = await fetch(
    `${BASE_URL}/api/team/${encodeURIComponent(String(userId))}/role`,
    {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        ...buildAuthHeaders(),
      },
      body: JSON.stringify({ role }),
    },
  )
  return handleResponse<any>(res)
}

export async function getActivityLog(
  filters?: { page?: number },
): Promise<any> {
  const params = new URLSearchParams()
  if (filters?.page != null) params.set("page", String(filters.page))
  const qs = params.toString()
  const url = qs ? `${BASE_URL}/api/activity?${qs}` : `${BASE_URL}/api/activity`
  const res = await fetch(url, { headers: buildAuthHeaders() })
  return handleResponse<any>(res)
}

// ── User Settings ──────────────────────────────────

export async function updateUserProfile(data: object): Promise<any> {
  const res = await fetch(`${BASE_URL}/users/me`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      ...buildAuthHeaders(),
    },
    body: JSON.stringify(data),
  })
  return handleResponse<any>(res)
}

export async function updateUserSecurity(data: object): Promise<any> {
  const res = await fetch(`${BASE_URL}/users/me/security`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      ...buildAuthHeaders(),
    },
    body: JSON.stringify(data),
  })
  return handleResponse<any>(res)
}

export async function getTrainingModelsStatus(): Promise<{
  auto_train_enabled: boolean
  cooldown_seconds: number
  models: string[]
  models_count: number
  admin_only_details: boolean
}> {
  const res = await fetch(`${BASE_URL}/api/training/models/status`, {
    headers: buildAuthHeaders(),
  })
  return handleResponse(res)
}

export async function distillFromCloud(opts?: {
  topics?: string[]
  num_per_topic?: number
  auto_train?: boolean
}): Promise<{
  status: string
  total_samples: number
  gemini_samples: number
  deepseek_samples: number
  topics_covered: number
  output_file?: string
  training_triggered: boolean
}> {
  const res = await fetch(`${BASE_URL}/api/training/distill-from-cloud`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...buildAuthHeaders() },
    body: JSON.stringify(opts || {}),
  })
  return handleResponse(res)
}

// ── Shared Documents ────────────────────────────────

export async function shareDocumentWithProject(
  documentId: string,
  projectId: string,
): Promise<{ ok: boolean }> {
  const res = await fetch(
    `${BASE_URL}/api/documents/${encodeURIComponent(documentId)}/project`,
    {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        ...buildAuthHeaders(),
      },
      body: JSON.stringify({ project_id: projectId }),
    },
  )
  return handleResponse<{ ok: boolean }>(res)
}

export async function getSharedDocuments(): Promise<any> {
  const res = await fetch(`${BASE_URL}/api/me/documents?shared=true&page_size=200`, {
    headers: buildAuthHeaders(),
  })
  return handleResponse<any>(res)
}

export async function getProjectMembers(projectId: string): Promise<{ project_id: string; members: { id: number; display_name: string; email: string; role: string; role_in_project: string }[] }> {
  const res = await fetch(`${BASE_URL}/api/projects/${encodeURIComponent(projectId)}/members`, {
    headers: buildAuthHeaders(),
  })
  return handleResponse(res)
}

export async function askVision(imageFile: File, question: string): Promise<{ answer: string }> {
  const formData = new FormData()
  formData.append("image", imageFile)
  formData.append("user_query", question)
  const res = await fetch(`${BASE_URL}/api/vision/ask`, {
    method: "POST",
    headers: buildAuthHeaders(),
    body: formData,
  })
  return handleResponse<{ answer: string }>(res)
}

export async function transcribeAudio(audioBlob: Blob, language: string = "en"): Promise<{ text: string; language: string; model: string }> {
  const formData = new FormData()
  formData.append("audio", audioBlob, "recording.webm")
  formData.append("language", language)
  const res = await fetch(`${BASE_URL}/api/audio/transcribe`, {
    method: "POST",
    headers: buildAuthHeaders(),
    body: formData,
  })
  return handleResponse(res)
}

// ── Model Registry (Admin CRUD) ────────────────────

export async function getRegistryProviders(): Promise<RegistryListResponse> {
  const res = await fetch(`${BASE_URL}/api/models/registry`, {
    headers: buildAuthHeaders(),
  })
  return handleResponse<RegistryListResponse>(res)
}

export async function getRegistryFlat(): Promise<RegistryFlatResponse> {
  const res = await fetch(`${BASE_URL}/api/models/registry/flat`, {
    headers: buildAuthHeaders(),
  })
  return handleResponse<RegistryFlatResponse>(res)
}

export async function addRegistryProvider(
  payload: AddRegistryProviderPayload,
): Promise<RegistryProviderResponse> {
  const res = await fetch(`${BASE_URL}/api/models/registry`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...buildAuthHeaders(),
    },
    body: JSON.stringify(payload),
  })
  return handleResponse<RegistryProviderResponse>(res)
}

export async function updateRegistryProvider(
  providerId: string,
  payload: UpdateRegistryProviderPayload,
): Promise<RegistryProviderResponse> {
  const res = await fetch(
    `${BASE_URL}/api/models/registry/${encodeURIComponent(providerId)}`,
    {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        ...buildAuthHeaders(),
      },
      body: JSON.stringify(payload),
    },
  )
  return handleResponse<RegistryProviderResponse>(res)
}

export async function deleteRegistryProvider(
  providerId: string,
): Promise<{ ok: boolean }> {
  const res = await fetch(
    `${BASE_URL}/api/models/registry/${encodeURIComponent(providerId)}`,
    {
      method: "DELETE",
      headers: buildAuthHeaders(),
    },
  )
  return handleResponse<{ ok: boolean }>(res)
}

export async function addRegistryModel(
  providerId: string,
  payload: AddRegistryModelPayload,
): Promise<RegistryModelResponse> {
  const res = await fetch(
    `${BASE_URL}/api/models/registry/${encodeURIComponent(providerId)}/models`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...buildAuthHeaders(),
      },
      body: JSON.stringify(payload),
    },
  )
  return handleResponse<RegistryModelResponse>(res)
}

export async function deleteRegistryModel(
  providerId: string,
  modelId: string,
): Promise<{ ok: boolean }> {
  const res = await fetch(
    `${BASE_URL}/api/models/registry/${encodeURIComponent(providerId)}/models/${encodeURIComponent(modelId)}`,
    {
      method: "DELETE",
      headers: buildAuthHeaders(),
    },
  )
  return handleResponse<{ ok: boolean }>(res)
}

/* ══════════════════════════════════════════════════════════════════════════════
   Model Management v2 API (GitHub Copilot-style)
   ══════════════════════════════════════════════════════════════════════════════ */

export async function v2GetCatalog(): Promise<V2CatalogResponse> {
  const res = await fetch(`${BASE_URL}/api/models/v2/catalog`, {
    headers: buildAuthHeaders(),
  })
  return handleResponse<V2CatalogResponse>(res)
}

export async function v2ListProviders(): Promise<V2ProviderListResponse> {
  const res = await fetch(`${BASE_URL}/api/models/v2/providers`, {
    headers: buildAuthHeaders(),
  })
  return handleResponse<V2ProviderListResponse>(res)
}

export async function v2GetProvider(providerId: string): Promise<V2ProviderResponse> {
  const res = await fetch(`${BASE_URL}/api/models/v2/providers/${encodeURIComponent(providerId)}`, {
    headers: buildAuthHeaders(),
  })
  return handleResponse<V2ProviderResponse>(res)
}

export async function v2AddProvider(payload: {
  name: string; vendor?: string; base_url?: string; api_key_env?: string; description?: string; icon?: string
}): Promise<V2ProviderResponse> {
  const res = await fetch(`${BASE_URL}/api/models/v2/providers`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...buildAuthHeaders() },
    body: JSON.stringify(payload),
  })
  return handleResponse<V2ProviderResponse>(res)
}

export async function v2UpdateProvider(providerId: string, payload: Record<string, any>): Promise<V2ProviderResponse> {
  const res = await fetch(`${BASE_URL}/api/models/v2/providers/${encodeURIComponent(providerId)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", ...buildAuthHeaders() },
    body: JSON.stringify(payload),
  })
  return handleResponse<V2ProviderResponse>(res)
}

export async function v2DeleteProvider(providerId: string): Promise<{ ok: boolean }> {
  const res = await fetch(`${BASE_URL}/api/models/v2/providers/${encodeURIComponent(providerId)}`, {
    method: "DELETE",
    headers: buildAuthHeaders(),
  })
  return handleResponse<{ ok: boolean }>(res)
}

export async function v2ReorderProviders(providerIds: string[]): Promise<{ ok: boolean }> {
  const res = await fetch(`${BASE_URL}/api/models/v2/providers/reorder`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...buildAuthHeaders() },
    body: JSON.stringify({ providerIds }),
  })
  return handleResponse<{ ok: boolean }>(res)
}

export async function v2ListModels(providerId: string): Promise<V2ModelListResponse> {
  const res = await fetch(`${BASE_URL}/api/models/v2/providers/${encodeURIComponent(providerId)}/models`, { headers: buildAuthHeaders() })
  return handleResponse<V2ModelListResponse>(res)
}

export async function v2GetModel(providerId: string, modelId: string): Promise<V2ModelResponse> {
  const res = await fetch(`${BASE_URL}/api/models/v2/providers/${encodeURIComponent(providerId)}/models/${encodeURIComponent(modelId)}`, { headers: buildAuthHeaders() })
  return handleResponse<V2ModelResponse>(res)
}

export async function v2AddModel(providerId: string, payload: Record<string, any>): Promise<V2ModelResponse> {
  const res = await fetch(`${BASE_URL}/api/models/v2/providers/${encodeURIComponent(providerId)}/models`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...buildAuthHeaders() },
    body: JSON.stringify(payload),
  })
  return handleResponse<V2ModelResponse>(res)
}

export async function v2UpdateModel(providerId: string, modelId: string, payload: Record<string, any>): Promise<V2ModelResponse> {
  const res = await fetch(`${BASE_URL}/api/models/v2/providers/${encodeURIComponent(providerId)}/models/${encodeURIComponent(modelId)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", ...buildAuthHeaders() },
    body: JSON.stringify(payload),
  })
  return handleResponse<V2ModelResponse>(res)
}

export async function v2DeleteModel(providerId: string, modelId: string): Promise<{ ok: boolean }> {
  const res = await fetch(`${BASE_URL}/api/models/v2/providers/${encodeURIComponent(providerId)}/models/${encodeURIComponent(modelId)}`, {
    method: "DELETE",
    headers: buildAuthHeaders(),
  })
  return handleResponse<{ ok: boolean }>(res)
}

export async function v2SetModelState(providerId: string, modelId: string, state: string): Promise<V2ModelResponse> {
  const res = await fetch(`${BASE_URL}/api/models/v2/providers/${encodeURIComponent(providerId)}/models/${encodeURIComponent(modelId)}/state`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...buildAuthHeaders() },
    body: JSON.stringify({ state }),
  })
  return handleResponse<V2ModelResponse>(res)
}

export async function v2ToggleModel(providerId: string, modelId: string, enabled: boolean): Promise<V2ModelResponse & { enabled: boolean }> {
  const res = await fetch(`${BASE_URL}/api/models/v2/providers/${encodeURIComponent(providerId)}/models/${encodeURIComponent(modelId)}/toggle`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...buildAuthHeaders() },
    body: JSON.stringify({ enabled }),
  })
  return handleResponse<V2ModelResponse & { enabled: boolean }>(res)
}

export async function v2SetVisibility(providerId: string, modelId: string, visible: boolean): Promise<V2ModelResponse & { visible: boolean }> {
  const res = await fetch(`${BASE_URL}/api/models/v2/providers/${encodeURIComponent(providerId)}/models/${encodeURIComponent(modelId)}/visibility`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...buildAuthHeaders() },
    body: JSON.stringify({ visible }),
  })
  return handleResponse<V2ModelResponse & { visible: boolean }>(res)
}

export async function v2SetModelRoles(providerId: string, modelId: string, roles: string[]): Promise<V2ModelResponse> {
  const res = await fetch(`${BASE_URL}/api/models/v2/providers/${encodeURIComponent(providerId)}/models/${encodeURIComponent(modelId)}/roles`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...buildAuthHeaders() },
    body: JSON.stringify({ roles }),
  })
  return handleResponse<V2ModelResponse>(res)
}

export async function v2SetModelDepartments(providerId: string, modelId: string, departments: string[]): Promise<V2ModelResponse> {
  const res = await fetch(`${BASE_URL}/api/models/v2/providers/${encodeURIComponent(providerId)}/models/${encodeURIComponent(modelId)}/departments`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...buildAuthHeaders() },
    body: JSON.stringify({ departments }),
  })
  return handleResponse<V2ModelResponse>(res)
}

export async function v2GetTaskMapping(): Promise<V2TaskMappingResponse> {
  const res = await fetch(`${BASE_URL}/api/models/v2/task-mapping`, { headers: buildAuthHeaders() })
  return handleResponse<V2TaskMappingResponse>(res)
}

export async function v2SetTaskMapping(taskType: string, providerId: string, modelId: string): Promise<{ ok: boolean }> {
  const res = await fetch(`${BASE_URL}/api/models/v2/task-mapping/${encodeURIComponent(taskType)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", ...buildAuthHeaders() },
    body: JSON.stringify({ providerId, modelId }),
  })
  return handleResponse<{ ok: boolean }>(res)
}

export async function v2RemoveTaskMapping(taskType: string): Promise<{ ok: boolean }> {
  const res = await fetch(`${BASE_URL}/api/models/v2/task-mapping/${encodeURIComponent(taskType)}`, {
    method: "DELETE",
    headers: buildAuthHeaders(),
  })
  return handleResponse<{ ok: boolean }>(res)
}

export async function v2GetRoutingStatus(): Promise<V2RoutingStatusResponse> {
  const res = await fetch(`${BASE_URL}/api/models/v2/routing/status`, { headers: buildAuthHeaders() })
  return handleResponse<V2RoutingStatusResponse>(res)
}

export async function v2ToggleRouting(enabled: boolean): Promise<V2RoutingStatusResponse> {
  const res = await fetch(`${BASE_URL}/api/models/v2/routing/toggle`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...buildAuthHeaders() },
    body: JSON.stringify({ enabled }),
  })
  return handleResponse<V2RoutingStatusResponse>(res)
}

export async function v2GetHealth(): Promise<V2HealthResponse> {
  const res = await fetch(`${BASE_URL}/api/models/v2/health`, { headers: buildAuthHeaders() })
  return handleResponse<V2HealthResponse>(res)
}

export async function v2GetMarketplace(): Promise<{ catalog: any[] }> {
  const res = await fetch(`${BASE_URL}/api/models/v2/marketplace`, { headers: buildAuthHeaders() })
  return handleResponse<{ catalog: any[] }>(res)
}

export async function v2GetAudit(limit: number = 100, action?: string): Promise<V2AuditResponse> {
  const params = new URLSearchParams({ limit: String(limit) })
  if (action) params.set("action", action)
  const res = await fetch(`${BASE_URL}/api/models/v2/audit?${params}`, { headers: buildAuthHeaders() })
  return handleResponse<V2AuditResponse>(res)
}

export async function v2GetReference(): Promise<V2ReferenceResponse> {
  const res = await fetch(`${BASE_URL}/api/models/v2/ref`, { headers: buildAuthHeaders() })
  return handleResponse<V2ReferenceResponse>(res)
}

export async function v2GetVisibleChatModels(): Promise<V2VisibleChatModelsResponse> {
  const res = await fetch(`${BASE_URL}/api/models/v2/chat/models`, { headers: buildAuthHeaders() })
  return handleResponse<V2VisibleChatModelsResponse>(res)
}

