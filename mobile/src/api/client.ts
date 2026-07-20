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
  V2CatalogResponse,
  V2ProviderListResponse,
  V2ProviderResponse,
  V2ModelListResponse,
  V2ModelResponse,
  V2TaskMappingResponse,
  V2HealthResponse,
  V2AuditResponse,
  V2ReferenceResponse,
  V2VisibleChatModelsResponse,
  V2RoutingStatusResponse,
  V2RoutingSelectResponse,
} from "../types/api"
import AsyncStorage from "@react-native-async-storage/async-storage"

// Use environment variable or fallback to network IP
const BASE_URL =
  process.env.EXPO_PUBLIC_API_BASE_URL ?? 
  "http://172.16.4.60:8000"

// Log the API URL for debugging
console.log("API Base URL:", BASE_URL)

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
      await clearAuthToken()
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
            "You don't have access to this project. Please request access or contact the admin.",
            403,
            parsed,
          )
        }
      }
      const detail = parsed?.detail
      const detailStr = typeof detail === 'string' ? detail : null
      const msg = parsed?.message ?? (typeof detail === 'object' ? detail?.message : null) ?? detailStr ?? null
      const err = parsed?.error ?? (typeof detail === 'object' ? detail?.error : null) ?? (typeof detail === 'string' ? detail : null) ?? null
      if (typeof msg === "string" && msg.trim()) {
        throw new ApiError(msg, res.status, parsed)
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

async function getAuthToken(): Promise<string | null> {
  return AsyncStorage.getItem(AUTH_TOKEN_KEY)
}

export async function setAuthToken(token: string) {
  await AsyncStorage.setItem(AUTH_TOKEN_KEY, token)
}

export async function clearAuthToken() {
  await AsyncStorage.removeItem(AUTH_TOKEN_KEY)
}

async function buildAuthHeaders() {
  const token = await getAuthToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export async function checkBackendConnection(
  timeoutMs = 5_000,
): Promise<{ ok: boolean; error?: string }> {
  try {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), timeoutMs)
    const res = await fetch(`${BASE_URL}/healthz`, {
      method: "GET",
      signal: controller.signal,
    })
    clearTimeout(timer)
    if (!res.ok) {
      return { ok: false, error: `Server returned ${res.status}` }
    }
    return { ok: true }
  } catch (err: any) {
    if (err?.name === "AbortError") {
      return { ok: false, error: "Connection timed out. Server is not responding." }
    }
    return { ok: false, error: err?.message ?? "Unable to reach server." }
  }
}

/**
 * Detailed health check that diagnoses specific service issues.
 * Mirrors the frontend's checkDetailedHealth for mobile use.
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
  // Step 1: Check if backend is running
  let backendRunning = false
  try {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), timeoutMs)
    const res = await fetch(`${BASE_URL}/healthz`, { method: "GET", signal: controller.signal })
    clearTimeout(timer)
    backendRunning = res.ok
  } catch {
    backendRunning = false
  }

  if (!backendRunning) {
    return {
      ok: false,
      error: "Backend server is not running.",
      backendRunning: false,
      ollamaRunning: false,
      hasExternalServices: false,
    }
  }

  // Step 2: Check Ollama status
  let ollamaRunning = false
  let ollamaError: string | undefined
  try {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), 5_000)
    const res = await fetch(`${BASE_URL}/api/health/ollama`, { method: "GET", signal: controller.signal })
    clearTimeout(timer)
    if (res.ok) {
      const data = await res.json()
      ollamaRunning = data?.ok ?? false
      if (!ollamaRunning && data?.hint) {
        ollamaError = data.hint
      }
    }
  } catch {
    ollamaRunning = false
  }

  // Step 3: Check if external services are configured
  let hasExternalServices = false
  try {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), 5_000)
    const res = await fetch(`${BASE_URL}/api/models/available`, { method: "GET", signal: controller.signal })
    clearTimeout(timer)
    if (res.ok) {
      const data = await res.json()
      hasExternalServices = Array.isArray(data) && data.length > 0
    }
  } catch {
    hasExternalServices = false
  }

  return {
    ok: backendRunning,
    backendRunning,
    ollamaRunning,
    ollamaError,
    hasExternalServices,
  }
}

export async function login(payload: LoginRequest): Promise<LoginResponse> {
  try {
    console.log("Attempting login at:", `${BASE_URL}/auth/login`)
    const res = await fetch(`${BASE_URL}/auth/login`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    })
    console.log("Login response status:", res.status)
    return handleResponse<LoginResponse>(res)
  } catch (err: any) {
    console.error("Login fetch error:", err?.message || err)
    throw new ApiError(
      `Network error: ${err?.message || "Unable to reach backend at " + BASE_URL}`,
      0,
      { originalError: err }
    )
  }
}

export async function requestEmailOtp(
  payload: EmailOtpRequest,
): Promise<EmailOtpRequestResponse> {
  try {
    console.log(`here: ${JSON.stringify(payload)}`)
    console.log("Requesting email OTP at:", `${BASE_URL}/auth/email/request`)
    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), 15000) // 15 seconds for OTP
    console.log("Requesting email OTP at:", `now here`)
    const res = await fetch(`${BASE_URL}/auth/email/request`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
      signal: controller.signal,
    })
    clearTimeout(timeout)
    console.log("Email OTP response status:", res.status)
    return handleResponse<EmailOtpRequestResponse>(res)
  } catch (err: any) {
    console.error("Email OTP fetch error:", err?.message || err)
    const errorMsg = err?.name === "AbortError" 
      ? "Request timeout. Backend is taking too long to respond. Check your network connection and try again."
      : err?.message || "Unable to reach backend at " + BASE_URL
    throw new ApiError(
      `Network error: ${errorMsg}`,
      0,
      { originalError: err }
    )
  }
}

export async function verifyEmailOtp(
  payload: EmailOtpVerifyRequest,
): Promise<LoginResponse> {
  try {
    console.log("Verifying email OTP at:", `${BASE_URL}/auth/email/verify`)
    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), 15000) // 15 seconds for verification
    
    const res = await fetch(`${BASE_URL}/auth/email/verify`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
      signal: controller.signal,
    })
    clearTimeout(timeout)
    console.log("Email verify response status:", res.status)
    return handleResponse<LoginResponse>(res)
  } catch (err: any) {
    console.error("Email verify fetch error:", err?.message || err)
    const errorMsg = err?.name === "AbortError"
      ? "Request timeout. Backend is taking too long to respond. Check your network connection and try again."
      : err?.message || "Unable to reach backend"
    throw new ApiError(
      `Network error: ${errorMsg}`,
      0,
      { originalError: err }
    )
  }
}

export async function uploadDocument(
  fileUri: string,
  fileName: string,
  mimeType: string,
  metadata: {
    project_id?: string | null
    project_name?: string | null
    document_type?: string | null
    document_date?: string | null
  },
): Promise<DocumentCreateResponse> {
  const formData = new FormData()
  formData.append("file", {
    uri: fileUri,
    name: fileName,
    type: mimeType,
  } as any)

  if (metadata.project_id) {
    formData.append("project_id", metadata.project_id)
  }
  if (metadata.project_name) {
    formData.append("project_name", metadata.project_name)
  }
  if (metadata.document_type) {
    formData.append("document_type", metadata.document_type)
  }
  if (metadata.document_date) {
    formData.append("document_date", metadata.document_date)
  }

  const authHeaders = await buildAuthHeaders()
  const res = await fetch(`${BASE_URL}/documents`, {
    method: "POST",
    headers: authHeaders,
    body: formData,
  })
  return handleResponse<DocumentCreateResponse>(res)
}

export async function getDocumentPrompts(
  documentId: string,
): Promise<PromptListResponse> {
  const authHeaders = await buildAuthHeaders()
  const res = await fetch(`${BASE_URL}/documents/${documentId}/prompts`, {
    headers: authHeaders,
  })
  return handleResponse<PromptListResponse>(res)
}

export async function getIngestStatus(
  documentId: string,
): Promise<any> {
  const authHeaders = await buildAuthHeaders()
  const res = await fetch(`${BASE_URL}/api/ingest/status?document_id=${encodeURIComponent(documentId)}`, {
    headers: authHeaders,
  })
  return handleResponse<any>(res)
}

export async function chatWithDocument(
  documentId: string,
  payload: ChatRequest,
): Promise<ChatResponse> {
  const authHeaders = await buildAuthHeaders()
  const res = await fetch(`${BASE_URL}/api/ask/${documentId}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders,
    },
    body: JSON.stringify(payload),
  })
  return handleResponse<ChatResponse>(res)
}

export async function getUserHistory(
): Promise<SummaryHistoryResponse> {
  const authHeaders = await buildAuthHeaders()
  const res = await fetch(`${BASE_URL}/users/me/summary-history`, {
    headers: authHeaders,
  })
  return handleResponse<SummaryHistoryResponse>(res)
}

export async function getSummaryHistory(): Promise<SummaryHistoryResponse> {
  const authHeaders = await buildAuthHeaders()
  const res = await fetch(`${BASE_URL}/users/me/summary-history`, {
    headers: authHeaders,
  })
  return handleResponse<SummaryHistoryResponse>(res)
}

export async function getDocumentAnalysis(
  documentId: string,
): Promise<DocumentAnalysisResponse> {
  const authHeaders = await buildAuthHeaders()
  const res = await fetch(`${BASE_URL}/documents/${documentId}/analysis`, {
    headers: authHeaders,
  })
  return handleResponse<DocumentAnalysisResponse>(res)
}

export async function getProjectAnalysis(
  projectId: string,
): Promise<DocumentAnalysisResponse> {
  const authHeaders = await buildAuthHeaders()
  const res = await fetch(`${BASE_URL}/projects/${projectId}/analysis`, {
    headers: authHeaders,
  })
  return handleResponse<DocumentAnalysisResponse>(res)
}

export async function createProject(
  payload: ProjectCreateRequest,
): Promise<ProjectResponse> {
  const authHeaders = await buildAuthHeaders()
  const res = await fetch(`${BASE_URL}/api/projects`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders,
    },
    body: JSON.stringify(payload),
  })
  return handleResponse<ProjectResponse>(res)
}

export async function updateProject(
  projectId: string,
  payload: { name?: string },
): Promise<any> {
  const authHeaders = await buildAuthHeaders()
  const res = await fetch(`${BASE_URL}/api/projects/${encodeURIComponent(projectId)}`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders,
    },
    body: JSON.stringify(payload),
  })
  return handleResponse<any>(res)
}

export async function deleteProject(
  projectId: string,
): Promise<{ ok: boolean }> {
  const authHeaders = await buildAuthHeaders()
  const res = await fetch(`${BASE_URL}/api/projects/${encodeURIComponent(projectId)}`, {
    method: "DELETE",
    headers: authHeaders,
  })
  return handleResponse<{ ok: boolean }>(res)
}

export async function getProjects(): Promise<ProjectListResponse> {
  const authHeaders = await buildAuthHeaders()
  const res = await fetch(`${BASE_URL}/projects`, {
    headers: authHeaders,
  })
  return handleResponse<ProjectListResponse>(res)
}

export async function getWorkspaces(): Promise<any> {
  const authHeaders = await buildAuthHeaders()
  const res = await fetch(`${BASE_URL}/api/projects`, {
    headers: authHeaders,
  })
  return handleResponse<any>(res)
}

export async function getDocumentLibrary(filters?: Record<string, string>): Promise<any> {
  const authHeaders = await buildAuthHeaders()
  const params = new URLSearchParams()
  if (filters) {
    Object.entries(filters).forEach(([k, v]) => { if (v) params.set(k, v) })
  }
  const qs = params.toString()
  const url = qs ? `${BASE_URL}/api/documents?${qs}` : `${BASE_URL}/api/documents`
  const res = await fetch(url, { headers: authHeaders })
  return handleResponse<any>(res)
}

export async function getMe(): Promise<UserMeResponse> {
  const authHeaders = await buildAuthHeaders()
  const res = await fetch(`${BASE_URL}/users/me`, {
    headers: authHeaders,
  })
  return handleResponse<UserMeResponse>(res)
}

export async function logout(): Promise<void> {
  try {
    const authHeaders = await buildAuthHeaders()
    await fetch(`${BASE_URL}/auth/logout`, {
      method: "POST",
      headers: authHeaders,
    }).catch(() => {})
  } finally {
    await clearAuthToken()
  }
}

export async function getUiSettings(): Promise<any> {
  const authHeaders = await buildAuthHeaders()
  const res = await fetch(`${BASE_URL}/api/settings/ui`, {
    headers: authHeaders,
  })
  return handleResponse<any>(res)
}

export async function getMyDocuments(): Promise<MyDocumentsResponse> {
  const authHeaders = await buildAuthHeaders()
  const res = await fetch(`${BASE_URL}/api/me/documents`, {
    headers: authHeaders,
  })
  return handleResponse<MyDocumentsResponse>(res)
}

export async function getChatSessions(projectId?: string, limit: number = 50): Promise<ChatSessionsListResponse> {
  const authHeaders = await buildAuthHeaders()
  let url = `${BASE_URL}/api/chat/sessions?limit=${limit}`
  if (projectId) url += `&project_id=${projectId}`
  const res = await fetch(url, {
    headers: authHeaders,
  })
  return handleResponse<ChatSessionsListResponse>(res)
}

export async function createChatSession(
  documentId?: string | null,
  scope?: "global" | "project" | "document",
): Promise<ChatSessionCreateResponse> {
  const authHeaders = await buildAuthHeaders()
  const body: Record<string, any> = {}
  if (documentId) body.document_id = documentId
  if (scope) body.scope = scope
  const res = await fetch(`${BASE_URL}/api/chat/sessions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders,
    },
    body: JSON.stringify(body),
  })
  return handleResponse<ChatSessionCreateResponse>(res)
}

export async function getAvailableModels(): Promise<ModelsAvailableResponse> {
  const res = await fetch(`${BASE_URL}/api/models/available`, {
    headers: await buildAuthHeaders(),
  })
  return handleResponse<ModelsAvailableResponse>(res)
}

// ── Additional endpoints for feature parity with frontend ──

export async function getModelCapabilities(): Promise<{
  capabilities: Record<string, string[]>
  labels: Record<string, string>
}> {
  const res = await fetch(`${BASE_URL}/api/models/capabilities`, {
    headers: await buildAuthHeaders(),
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
  )
  return handleResponse<{
    model_id: string
    capabilities: string[]
    display_category: string
  }>(res)
}

export async function getModelLabels(): Promise<{ labels: Record<string, string> }> {
  const authHeaders = await buildAuthHeaders()
  const res = await fetch(`${BASE_URL}/api/models/labels`, {
    headers: authHeaders,
  })
  return handleResponse<{ labels: Record<string, string> }>(res)
}

export async function getMyProjects(): Promise<any> {
  const authHeaders = await buildAuthHeaders()
  const res = await fetch(`${BASE_URL}/api/me/projects`, {
    headers: authHeaders,
  })
  return handleResponse<any>(res)
}

export async function overrideDocumentProjectAPI(documentId: string, projectId: string): Promise<{ ok: boolean }> {
  const authHeaders = await buildAuthHeaders()
  const res = await fetch(`${BASE_URL}/api/documents/${encodeURIComponent(documentId)}/project`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders,
    },
    body: JSON.stringify({ project_id: projectId }),
  })
  return handleResponse<{ ok: boolean }>(res)
}

export async function retryIngest(documentId: string): Promise<{ ok: boolean }> {
  const authHeaders = await buildAuthHeaders()
  const res = await fetch(`${BASE_URL}/api/ingest/retry`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders,
    },
    body: JSON.stringify({ document_id: documentId }),
  })
  return handleResponse<{ ok: boolean }>(res)
}

export async function downloadDocumentFileApi(documentId: string): Promise<Blob> {
  const authHeaders = await buildAuthHeaders()
  const res = await fetch(`${BASE_URL}/api/documents/${encodeURIComponent(documentId)}/download`, {
    headers: authHeaders,
  })
  if (!res.ok) throw new ApiError(`Failed to download: ${res.statusText}`, res.status, null)
  return res.blob()
}

// Already implemented above as getChatSessions()

export async function chatGlobally(
  payload: ChatRequest,
  timeoutMs: number = 120_000,
): Promise<ChatResponse> {
  const authHeaders = await buildAuthHeaders()
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs)

  try {
    const res = await fetch(`${BASE_URL}/api/ask`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...authHeaders,
      },
      body: JSON.stringify(payload),
      signal: controller.signal,
    })
    clearTimeout(timeoutId)
    return handleResponse<ChatResponse>(res)
  } catch (err: any) {
    clearTimeout(timeoutId)
    if (err?.name === "AbortError") {
      throw new ApiError(
        "Request timed out. The AI model did not respond within the time limit.",
        0,
        { error: "timeout" },
      )
    }
    throw err
  }
}

// ══════════════════════════════════════════════════════════════════════════════
// SSE Streaming chat — mirrors the web frontend's chatGloballyStream
// ══════════════════════════════════════════════════════════════════════════════

export interface StreamCallbacks {
  onChunk: (chunk: string, model: string, sessionId: string) => void
  onReasoning?: (reasoning: string, model: string, sessionId: string) => void
  onDone: (fullText: string, model: string, sessionId: string) => void
  onError: (error: string) => void
}

/**
 * Send a streaming chat request using SSE (Server-Sent Events) via fetch + ReadableStream.
 * Falls back to the non-streaming endpoint if ReadableStream is not available.
 */
export async function chatGloballyStream(
  payload: ChatRequest,
  callbacks: StreamCallbacks,
  timeoutMs: number = 120_000,
): Promise<void> {
  const authHeaders = await buildAuthHeaders()
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs)

  try {
    const res = await fetch(`${BASE_URL}/api/ask/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...authHeaders,
      },
      body: JSON.stringify(payload),
      signal: controller.signal,
    })

    if (!res.ok) {
      clearTimeout(timeoutId)
      const errText = await res.text().catch(() => "")
      let errMsg: string
      try {
        const parsed = JSON.parse(errText)
        errMsg = parsed.error || parsed.message || `HTTP ${res.status}`
      } catch {
        errMsg = `HTTP ${res.status}${errText ? ": " + errText : ""}`
      }
      callbacks.onError(errMsg)
      return
    }

    const reader = res.body?.getReader()
    if (!reader) {
      clearTimeout(timeoutId)
      // ReadableStream not available — fall back to non-streaming
      try {
        const fallbackRes = await chatGlobally(payload)
        const ans = (fallbackRes as any).answer || ""
        if (ans) {
          callbacks.onChunk(ans, "", "")
        }
        callbacks.onDone(ans, "", "")
      } catch (fallbackErr: any) {
        callbacks.onError(fallbackErr?.message || "Fallback failed")
      }
      return
    }

    const decoder = new TextDecoder()
    let buffer = ""
    let fullText = ""
    let model = ""
    let sessionId = ""

    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split("\n")
        buffer = lines.pop() || ""

        for (const line of lines) {
          const trimmed = line.trim()
          if (!trimmed.startsWith("data: ")) continue
          const dataPayload = trimmed.slice(6).trim()

          if (dataPayload === "[DONE]") {
            clearTimeout(timeoutId)
            callbacks.onDone(fullText, model, sessionId)
            return
          }

          try {
            const data = JSON.parse(dataPayload)
            if (data.error) {
              clearTimeout(timeoutId)
              callbacks.onError(data.error)
              return
            }
            model = data.model || model
            sessionId = data.session_id || sessionId
            if (data.type === "reasoning") {
              if (callbacks.onReasoning) {
                callbacks.onReasoning(data.content || "", model, sessionId)
              }
            } else if (data.type === "content") {
              fullText += data.content || ""
              callbacks.onChunk(data.content || "", model, sessionId)
            } else if (data.chunk) {
              // Legacy backward-compat format
              fullText += data.chunk
              callbacks.onChunk(data.chunk, model, sessionId)
            }
          } catch {
            // skip malformed JSON lines
          }
        }
      }
    } catch (readErr: any) {
      clearTimeout(timeoutId)
      if (readErr?.name !== "AbortError") {
        callbacks.onError(readErr?.message || "Stream read error")
      }
      return
    }

    clearTimeout(timeoutId)
    callbacks.onDone(fullText, model, sessionId)
  } catch (err: any) {
    clearTimeout(timeoutId)
    if (err?.name === "AbortError") {
      callbacks.onError("Request timed out. The AI model did not respond within the time limit.")
    } else {
      callbacks.onError(err?.message || "Failed to get streaming response")
    }
  }
}

export async function suggestPrompts(
  documentId: string,
): Promise<{ prompts: string[]; groups?: any[]; scope?: string }> {
  const authHeaders = await buildAuthHeaders()
  const res = await fetch(
    `${BASE_URL}/api/prompts/suggest?document_id=${encodeURIComponent(documentId)}`,
    { headers: authHeaders },
  )
  return handleResponse<{ prompts: string[]; groups?: any[]; scope?: string }>(res)
}

export async function flowchartGenerate(payload: { text: string; diagram_type?: string; model?: string }): Promise<{ mermaid: string; drawing_prompt: string }> {
  const authHeaders = await buildAuthHeaders()
  const res = await fetch(`${BASE_URL}/api/flowchart/generate`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders,
    },
    body: JSON.stringify(payload),
  })
  return handleResponse<{ mermaid: string; drawing_prompt: string }>(res)
}

export async function chartsAnalyze(file: File): Promise<any> {
  const authHeaders = await buildAuthHeaders()
  const formData = new FormData()
  formData.append("file", file)
  const res = await fetch(`${BASE_URL}/api/charts/analyze`, {
    method: "POST",
    headers: authHeaders,
    body: formData,
  })
  return handleResponse<any>(res)
}

export async function chartsBuild(payload: {
  file?: File
  columns?: string[]
  numeric_columns?: string[]
  x_column?: string
  y_columns?: string[]
  chart_type?: string
}): Promise<any> {
  const authHeaders = await buildAuthHeaders()
  const formData = new FormData()
  if (payload.file) formData.append("file", payload.file)
  if (payload.columns) formData.append("columns", JSON.stringify(payload.columns))
  if (payload.numeric_columns) formData.append("numeric_columns", JSON.stringify(payload.numeric_columns))
  if (payload.x_column) formData.append("x_column", payload.x_column)
  if (payload.y_columns) formData.append("y_columns", JSON.stringify(payload.y_columns))
  if (payload.chart_type) formData.append("chart_type", payload.chart_type)

  const res = await fetch(`${BASE_URL}/api/charts/build`, {
    method: "POST",
    headers: authHeaders,
    body: formData,
  })
  return handleResponse<any>(res)
}

export async function getModelPullStatus(model: string): Promise<any> {
  const authHeaders = await buildAuthHeaders()
  const res = await fetch(`${BASE_URL}/api/models/pull/status/${encodeURIComponent(model)}`, {
    headers: authHeaders,
  })
  return handleResponse<any>(res)
}

export async function getBootstrapStatus(): Promise<any> {
  const authHeaders = await buildAuthHeaders()
  const res = await fetch(`${BASE_URL}/api/bootstrap/status`, {
    headers: authHeaders,
  })
  return handleResponse<any>(res)
}

export async function getChatMessages(
  sessionId: string,
  limit: number = 100,
): Promise<ChatMessagesResponse> {
  const authHeaders = await buildAuthHeaders()
  const res = await fetch(
    `${BASE_URL}/api/chat/sessions/${encodeURIComponent(sessionId)}/messages?limit=${encodeURIComponent(
      String(limit),
    )}`,
    {
      headers: authHeaders,
    },
  )
  return handleResponse<ChatMessagesResponse>(res)
}

export async function setChatSessionModel(
  sessionId: string,
  model: string,
): Promise<{ ok: boolean; session_id: string; model: string }> {
  const authHeaders = await buildAuthHeaders()
  const res = await fetch(`${BASE_URL}/api/chat/sessions/${encodeURIComponent(sessionId)}/model`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders,
    },
    body: JSON.stringify({ model }),
  })
  return handleResponse<{ ok: boolean; session_id: string; model: string }>(res)
}

export async function deleteChatSession(sessionId: string): Promise<{ ok: boolean }> {
  const authHeaders = await buildAuthHeaders()
  const res = await fetch(`${BASE_URL}/api/chat/sessions/${encodeURIComponent(sessionId)}`, {
    method: "DELETE",
    headers: authHeaders,
  })
  return handleResponse<{ ok: boolean }>(res)
}

export async function patchChatSession(
  sessionId: string,
  payload: { title?: string; model?: string },
): Promise<{ ok: boolean }> {
  const authHeaders = await buildAuthHeaders()
  const res = await fetch(`${BASE_URL}/api/chat/sessions/${encodeURIComponent(sessionId)}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders,
    },
    body: JSON.stringify(payload),
  })
  return handleResponse<{ ok: boolean }>(res)
}

export async function startModelPull(
  model: string,
  resume: boolean = true,
): Promise<ModelPullStatusResponse> {
  const authHeaders = await buildAuthHeaders()
  const res = await fetch(`${BASE_URL}/api/models/pull`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders,
    },
    body: JSON.stringify({ model, resume }),
  })
  return handleResponse<ModelPullStatusResponse>(res)
}

export async function downloadDocumentFile(documentId: string): Promise<Blob> {
  const authHeaders = await buildAuthHeaders()
  const res = await fetch(`${BASE_URL}/documents/${encodeURIComponent(documentId)}/file`, {
    headers: authHeaders,
  })
  if (!res.ok) throw new ApiError(`Failed to download: ${res.statusText}`, res.status, null)
  return res.blob()
}



export async function getProcessingStatus(documentId: string): Promise<any> {
  const authHeaders = await buildAuthHeaders()
  const res = await fetch(`${BASE_URL}/api/ingest/${encodeURIComponent(documentId)}/status`, {
    headers: authHeaders,
  })
  return handleResponse<any>(res)
}

export async function runExtraction(schema: string, documentIds: string[]): Promise<any> {
  const authHeaders = await buildAuthHeaders()
  const res = await fetch(`${BASE_URL}/api/analyze/extraction`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders,
    },
    body: JSON.stringify({ schema, document_ids: documentIds }),
  })
  return handleResponse<any>(res)
}

export async function generateSummary(documentIds: string[]): Promise<any> {
  const authHeaders = await buildAuthHeaders()
  const res = await fetch(`${BASE_URL}/api/analyze/summaries`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders,
    },
    body: JSON.stringify({ document_ids: documentIds }),
  })
  return handleResponse<any>(res)
}

export async function classifyDocuments(rules: string, documentIds?: string[]): Promise<any> {
  const authHeaders = await buildAuthHeaders()
  const res = await fetch(`${BASE_URL}/api/analyze/classification`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders,
    },
    body: JSON.stringify({ rules, document_ids: documentIds }),
  })
  return handleResponse<any>(res)
}

export async function compareDocuments(docA: string, docB: string): Promise<any> {
  const authHeaders = await buildAuthHeaders()
  const res = await fetch(`${BASE_URL}/api/analyze/compare`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders,
    },
    body: JSON.stringify({ doc_a: docA, doc_b: docB }),
  })
  return handleResponse<any>(res)
}

export async function getOutputs(filters?: Record<string, string>): Promise<any> {
  const authHeaders = await buildAuthHeaders()
  let url = `${BASE_URL}/api/outputs`
  if (filters) {
    const params = Object.entries(filters)
      .filter(([, v]) => v !== undefined && v !== null)
      .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
      .join("&")
    if (params) url += `?${params}`
  }
  const res = await fetch(url, { headers: authHeaders })
  return handleResponse<any>(res)
}

export async function exportOutput(outputId: string, format: string): Promise<any> {
  const authHeaders = await buildAuthHeaders()
  const res = await fetch(
    `${BASE_URL}/api/outputs/${encodeURIComponent(outputId)}/export?format=${encodeURIComponent(format)}`,
    { headers: authHeaders },
  )
  return handleResponse<any>(res)
}

export async function setDefaultModel(taskType: string, modelId: string): Promise<any> {
  const authHeaders = await buildAuthHeaders()
  const res = await fetch(`${BASE_URL}/admin/models/default`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders,
    },
    body: JSON.stringify({ task_type: taskType, model_id: modelId }),
  })
  return handleResponse<any>(res)
}

export async function savePrompt(promptType: string, content: string): Promise<any> {
  const authHeaders = await buildAuthHeaders()
  const res = await fetch(`${BASE_URL}/admin/prompts`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders,
    },
    body: JSON.stringify({ prompt_type: promptType, content }),
  })
  return handleResponse<any>(res)
}

export async function getPrompts(): Promise<any> {
  const authHeaders = await buildAuthHeaders()
  const res = await fetch(`${BASE_URL}/admin/prompts`, { headers: authHeaders })
  return handleResponse<any>(res)
}

export async function updateIntegrationSettings(config: object): Promise<any> {
  const authHeaders = await buildAuthHeaders()
  const res = await fetch(`${BASE_URL}/admin/integrations`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders,
    },
    body: JSON.stringify(config),
  })
  return handleResponse<any>(res)
}

export async function getTeamMembers(): Promise<any> {
  const authHeaders = await buildAuthHeaders()
  const res = await fetch(`${BASE_URL}/api/team`, { headers: authHeaders })
  return handleResponse<any>(res)
}

export async function updateMemberRole(userId: number, role: string): Promise<any> {
  const authHeaders = await buildAuthHeaders()
  const res = await fetch(`${BASE_URL}/api/team/${userId}/role`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders,
    },
    body: JSON.stringify({ role }),
  })
  return handleResponse<any>(res)
}

export async function getActivityLog(filters?: Record<string, string>): Promise<any> {
  const authHeaders = await buildAuthHeaders()
  let url = `${BASE_URL}/api/activity`
  if (filters) {
    const params = Object.entries(filters)
      .filter(([, v]) => v !== undefined && v !== null)
      .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
      .join("&")
    if (params) url += `?${params}`
  }
  const res = await fetch(url, { headers: authHeaders })
  return handleResponse<any>(res)
}

export async function updateUserProfile(data: object): Promise<any> {
  const authHeaders = await buildAuthHeaders()
  const res = await fetch(`${BASE_URL}/users/me`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders,
    },
    body: JSON.stringify(data),
  })
  return handleResponse<any>(res)
}

export async function updateUserSecurity(data: object): Promise<any> {
  const authHeaders = await buildAuthHeaders()
  const res = await fetch(`${BASE_URL}/users/me/security`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders,
    },
    body: JSON.stringify(data),
  })
  return handleResponse<any>(res)
}

export async function saveUserThemePreference(theme: string): Promise<any> {
  const res = await fetch(`${BASE_URL}/api/settings/ui`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(await buildAuthHeaders()),
    },
    body: JSON.stringify({ theme }),
  })
  return handleResponse<any>(res)
}

export async function askVision(
  imageUri: string,
  question: string,
): Promise<{ answer: string }> {
  const formData = new FormData()
  const filename = imageUri.split("/").pop() || "image.jpg"
  const ext = filename.split(".").pop()?.toLowerCase() || "jpg"
  const mimeType = ext === "png" ? "image/png" : ext === "webp" ? "image/webp" : "image/jpeg"
  formData.append("image", {
    uri: imageUri,
    name: filename,
    type: mimeType,
  } as any)
  formData.append("user_query", question)
  const authHeaders = await buildAuthHeaders()
  const res = await fetch(`${BASE_URL}/api/vision/ask`, {
    method: "POST",
    headers: authHeaders,
    body: formData,
  })
  return handleResponse<{ answer: string }>(res)
}

export async function getRandomPromptSuggestions(
  count: number = 6,
): Promise<{ suggestions: { id: number; title: string; prompt_text: string; icon: string; category: string }[]; count: number }> {
  const authHeaders = await buildAuthHeaders()
  const res = await fetch(`${BASE_URL}/api/prompt-suggestions/random?count=${encodeURIComponent(String(count))}`, {
    headers: authHeaders,
  })
  return handleResponse<{ suggestions: { id: number; title: string; prompt_text: string; icon: string; category: string }[]; count: number }>(res)
}

export async function transcribeAudio(
  fileUri: string,
  fileName: string,
  mimeType: string,
  language: string = "en",
): Promise<{ text: string; language: string; model: string }> {
  const formData = new FormData()
  formData.append("audio", {
    uri: fileUri,
    name: fileName,
    type: mimeType,
  } as any)
  formData.append("language", language)
  const authHeaders = await buildAuthHeaders()
  const res = await fetch(`${BASE_URL}/api/audio/transcribe`, {
    method: "POST",
    headers: authHeaders,
    body: formData,
  })
  return handleResponse<{ text: string; language: string; model: string }>(res)
}

export async function distillFromCloud(opts?: {
  topics?: string[]
  num_per_topic?: number
  auto_train?: boolean
}): Promise<any> {
  const res = await fetch(`${BASE_URL}/api/training/distill-from-cloud`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(await buildAuthHeaders()) },
    body: JSON.stringify(opts || {}),
  })
  return handleResponse<any>(res)
}

/* ══════════════════════════════════════════════════════════════════════════════
   Model Management v2 API
   ══════════════════════════════════════════════════════════════════════════════ */

export async function v2GetCatalog(): Promise<V2CatalogResponse> {
  const res = await fetch(`${BASE_URL}/api/models/v2/catalog`, {
    headers: await buildAuthHeaders(),
  })
  return handleResponse<V2CatalogResponse>(res)
}

export async function v2ListProviders(): Promise<V2ProviderListResponse> {
  const res = await fetch(`${BASE_URL}/api/models/v2/providers`, {
    headers: await buildAuthHeaders(),
  })
  return handleResponse<V2ProviderListResponse>(res)
}

export async function v2GetProvider(providerId: string): Promise<V2ProviderResponse> {
  const res = await fetch(`${BASE_URL}/api/models/v2/providers/${encodeURIComponent(providerId)}`, {
    headers: await buildAuthHeaders(),
  })
  return handleResponse<V2ProviderResponse>(res)
}

export async function v2AddProvider(payload: {
  name: string; vendor?: string; base_url?: string; description?: string; icon?: string
}): Promise<V2ProviderResponse> {
  const res = await fetch(`${BASE_URL}/api/models/v2/providers`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(await buildAuthHeaders()) },
    body: JSON.stringify(payload),
  })
  return handleResponse<V2ProviderResponse>(res)
}

export async function v2UpdateProvider(providerId: string, payload: Record<string, any>): Promise<V2ProviderResponse> {
  const res = await fetch(`${BASE_URL}/api/models/v2/providers/${encodeURIComponent(providerId)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", ...(await buildAuthHeaders()) },
    body: JSON.stringify(payload),
  })
  return handleResponse<V2ProviderResponse>(res)
}

export async function v2DeleteProvider(providerId: string): Promise<{ ok: boolean }> {
  const res = await fetch(`${BASE_URL}/api/models/v2/providers/${encodeURIComponent(providerId)}`, {
    method: "DELETE",
    headers: await buildAuthHeaders(),
  })
  return handleResponse<{ ok: boolean }>(res)
}

export async function v2ReorderProviders(providerIds: string[]): Promise<{ ok: boolean }> {
  const res = await fetch(`${BASE_URL}/api/models/v2/providers/reorder`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(await buildAuthHeaders()) },
    body: JSON.stringify({ providerIds }),
  })
  return handleResponse<{ ok: boolean }>(res)
}

export async function v2ListModels(providerId: string): Promise<V2ModelListResponse> {
  const res = await fetch(`${BASE_URL}/api/models/v2/providers/${encodeURIComponent(providerId)}/models`, {
    headers: await buildAuthHeaders(),
  })
  return handleResponse<V2ModelListResponse>(res)
}

export async function v2GetModel(providerId: string, modelId: string): Promise<V2ModelResponse> {
  const res = await fetch(`${BASE_URL}/api/models/v2/providers/${encodeURIComponent(providerId)}/models/${encodeURIComponent(modelId)}`, {
    headers: await buildAuthHeaders(),
  })
  return handleResponse<V2ModelResponse>(res)
}

export async function v2AddModel(providerId: string, payload: Record<string, any>): Promise<V2ModelResponse> {
  const res = await fetch(`${BASE_URL}/api/models/v2/providers/${encodeURIComponent(providerId)}/models`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(await buildAuthHeaders()) },
    body: JSON.stringify(payload),
  })
  return handleResponse<V2ModelResponse>(res)
}

export async function v2UpdateModel(providerId: string, modelId: string, payload: Record<string, any>): Promise<V2ModelResponse> {
  const res = await fetch(`${BASE_URL}/api/models/v2/providers/${encodeURIComponent(providerId)}/models/${encodeURIComponent(modelId)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", ...(await buildAuthHeaders()) },
    body: JSON.stringify(payload),
  })
  return handleResponse<V2ModelResponse>(res)
}

export async function v2DeleteModel(providerId: string, modelId: string): Promise<{ ok: boolean }> {
  const res = await fetch(`${BASE_URL}/api/models/v2/providers/${encodeURIComponent(providerId)}/models/${encodeURIComponent(modelId)}`, {
    method: "DELETE",
    headers: await buildAuthHeaders(),
  })
  return handleResponse<{ ok: boolean }>(res)
}

export async function v2SetModelState(providerId: string, modelId: string, state: string): Promise<V2ModelResponse> {
  const res = await fetch(`${BASE_URL}/api/models/v2/providers/${encodeURIComponent(providerId)}/models/${encodeURIComponent(modelId)}/state`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(await buildAuthHeaders()) },
    body: JSON.stringify({ state }),
  })
  return handleResponse<V2ModelResponse>(res)
}

export async function v2ToggleModel(providerId: string, modelId: string, enabled: boolean): Promise<V2ModelResponse & { enabled: boolean }> {
  const res = await fetch(`${BASE_URL}/api/models/v2/providers/${encodeURIComponent(providerId)}/models/${encodeURIComponent(modelId)}/toggle`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(await buildAuthHeaders()) },
    body: JSON.stringify({ enabled }),
  })
  return handleResponse<V2ModelResponse & { enabled: boolean }>(res)
}

export async function v2SetVisibility(providerId: string, modelId: string, visible: boolean): Promise<V2ModelResponse & { visible: boolean }> {
  const res = await fetch(`${BASE_URL}/api/models/v2/providers/${encodeURIComponent(providerId)}/models/${encodeURIComponent(modelId)}/visibility`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(await buildAuthHeaders()) },
    body: JSON.stringify({ visible }),
  })
  return handleResponse<V2ModelResponse & { visible: boolean }>(res)
}

export async function v2SetModelRoles(providerId: string, modelId: string, roles: string[]): Promise<V2ModelResponse> {
  const res = await fetch(`${BASE_URL}/api/models/v2/providers/${encodeURIComponent(providerId)}/models/${encodeURIComponent(modelId)}/roles`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(await buildAuthHeaders()) },
    body: JSON.stringify({ roles }),
  })
  return handleResponse<V2ModelResponse>(res)
}

export async function v2SetModelDepartments(providerId: string, modelId: string, departments: string[]): Promise<V2ModelResponse> {
  const res = await fetch(`${BASE_URL}/api/models/v2/providers/${encodeURIComponent(providerId)}/models/${encodeURIComponent(modelId)}/departments`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(await buildAuthHeaders()) },
    body: JSON.stringify({ departments }),
  })
  return handleResponse<V2ModelResponse>(res)
}

export async function v2GetTaskMapping(): Promise<V2TaskMappingResponse> {
  const res = await fetch(`${BASE_URL}/api/models/v2/task-mapping`, {
    headers: await buildAuthHeaders(),
  })
  return handleResponse<V2TaskMappingResponse>(res)
}

export async function v2SetTaskMapping(taskType: string, providerId: string, modelId: string): Promise<{ ok: boolean }> {
  const res = await fetch(`${BASE_URL}/api/models/v2/task-mapping/${encodeURIComponent(taskType)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", ...(await buildAuthHeaders()) },
    body: JSON.stringify({ providerId, modelId }),
  })
  return handleResponse<{ ok: boolean }>(res)
}

export async function v2RemoveTaskMapping(taskType: string): Promise<{ ok: boolean }> {
  const res = await fetch(`${BASE_URL}/api/models/v2/task-mapping/${encodeURIComponent(taskType)}`, {
    method: "DELETE",
    headers: await buildAuthHeaders(),
  })
  return handleResponse<{ ok: boolean }>(res)
}

export async function v2GetRoutingStatus(): Promise<V2RoutingStatusResponse> {
  const res = await fetch(`${BASE_URL}/api/models/v2/routing/status`, {
    headers: await buildAuthHeaders(),
  })
  return handleResponse<V2RoutingStatusResponse>(res)
}

export async function v2ToggleRouting(enabled: boolean): Promise<V2RoutingStatusResponse> {
  const res = await fetch(`${BASE_URL}/api/models/v2/routing/toggle`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(await buildAuthHeaders()) },
    body: JSON.stringify({ enabled }),
  })
  return handleResponse<V2RoutingStatusResponse>(res)
}

export async function v2GetHealth(): Promise<V2HealthResponse> {
  const res = await fetch(`${BASE_URL}/api/models/v2/health`, {
    headers: await buildAuthHeaders(),
  })
  return handleResponse<V2HealthResponse>(res)
}

export async function v2GetMarketplace(): Promise<{ catalog: any[] }> {
  const res = await fetch(`${BASE_URL}/api/models/v2/marketplace`, {
    headers: await buildAuthHeaders(),
  })
  return handleResponse<{ catalog: any[] }>(res)
}

export async function v2GetAudit(limit: number = 100, action?: string): Promise<V2AuditResponse> {
  const params = new URLSearchParams({ limit: String(limit) })
  if (action) params.set("action", action)
  const res = await fetch(`${BASE_URL}/api/models/v2/audit?${params}`, {
    headers: await buildAuthHeaders(),
  })
  return handleResponse<V2AuditResponse>(res)
}

export async function v2GetReference(): Promise<V2ReferenceResponse> {
  const res = await fetch(`${BASE_URL}/api/models/v2/ref`, {
    headers: await buildAuthHeaders(),
  })
  return handleResponse<V2ReferenceResponse>(res)
}

export async function v2GetVisibleChatModels(): Promise<V2VisibleChatModelsResponse> {
  const res = await fetch(`${BASE_URL}/api/models/v2/chat/models`, {
    headers: await buildAuthHeaders(),
  })
  return handleResponse<V2VisibleChatModelsResponse>(res)
}

export async function v2SelectModelForTask(taskType: string): Promise<V2RoutingSelectResponse> {
  const res = await fetch(`${BASE_URL}/api/models/v2/routing/select/${encodeURIComponent(taskType)}`, {
    headers: await buildAuthHeaders(),
  })
  return handleResponse<V2RoutingSelectResponse>(res)
}
