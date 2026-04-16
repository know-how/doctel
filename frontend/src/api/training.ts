/**
 * Training Room API functions.
 * These are appended to the main API client for keeping all API calls centralised.
 * Import from this file or from client.ts after re-export.
 */

const BASE_URL =
  (import.meta as any).env.VITE_API_BASE_URL ?? "http://localhost:8000"
const AUTH_TOKEN_KEY = "docintel_auth_token"

function buildAuthHeaders(): Record<string, string> {
  const token = typeof window !== "undefined" ? window.localStorage.getItem(AUTH_TOKEN_KEY) : null
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text().catch(() => "")
    throw new Error(text || res.statusText)
  }
  return (await res.json()) as T
}

// ── Training status ------------------------------------------------------------

export interface TrainingJobStatus {
  id: string
  trigger: string
  folder?: string
  status: "pending" | "running" | "done" | "error" | "skipped"
  progress: number
  message: string
  started_at?: string
  finished_at?: string
  result?: Record<string, any>
}

export interface TrainingStatusResponse {
  status: string
  job: TrainingJobStatus | null
}

export async function getTrainingStatus(): Promise<TrainingStatusResponse> {
  const res = await fetch(`${BASE_URL}/api/training/status`, {
    headers: buildAuthHeaders(),
  })
  return handleResponse<TrainingStatusResponse>(res)
}

// ── Training triggers ----------------------------------------------------------

export async function triggerTrainNow(): Promise<{ ok: boolean; job?: TrainingJobStatus; reason?: string }> {
  const res = await fetch(`${BASE_URL}/api/training/now`, {
    method: "POST",
    headers: buildAuthHeaders(),
  })
  return handleResponse(res)
}

export async function triggerTrainIdle(): Promise<{ ok: boolean; job?: TrainingJobStatus; reason?: string; free_mb?: number }> {
  const res = await fetch(`${BASE_URL}/api/training/idle`, {
    method: "POST",
    headers: buildAuthHeaders(),
  })
  return handleResponse(res)
}

export async function triggerTrainBatch(folder?: string): Promise<{ ok: boolean; job?: TrainingJobStatus; reason?: string }> {
  const res = await fetch(`${BASE_URL}/api/training/batch`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...buildAuthHeaders() },
    body: JSON.stringify(folder ? { folder } : {}),
  })
  return handleResponse(res)
}

// ── Training history -----------------------------------------------------------

export interface AdapterRecord {
  id: string
  created_at: string
  samples: number
  epochs: number
  notes: string
  path: string
}

export interface TrainingHistoryResponse {
  adapters: AdapterRecord[]
}

export async function getTrainingHistory(): Promise<TrainingHistoryResponse> {
  const res = await fetch(`${BASE_URL}/api/training/history`, {
    headers: buildAuthHeaders(),
  })
  return handleResponse<TrainingHistoryResponse>(res)
}

// ── Inbox management ----------------------------------------------------------

export interface InboxFile {
  name: string
  size_kb: number
  supported: boolean
}

export interface InboxListResponse {
  inbox: string
  files: InboxFile[]
}

export async function getInboxFiles(): Promise<InboxListResponse> {
  const res = await fetch(`${BASE_URL}/api/training/inbox`, {
    headers: buildAuthHeaders(),
  })
  return handleResponse<InboxListResponse>(res)
}

export async function uploadInboxFile(file: File): Promise<{ ok: boolean; filename: string; size_bytes: number }> {
  const form = new FormData()
  form.append("file", file)
  const res = await fetch(`${BASE_URL}/api/training/inbox`, {
    method: "POST",
    headers: buildAuthHeaders(),
    body: form,
  })
  return handleResponse(res)
}

// ── Router status -------------------------------------------------------------

export interface RouterStatusResponse {
  local_lora: boolean
  ollama: boolean
  cloud_teacher: boolean
  web_search: boolean
  active_ollama_model: string
  free_ram_mb: number
}

export async function getRouterStatus(): Promise<RouterStatusResponse> {
  const res = await fetch(`${BASE_URL}/api/router/status`, {
    headers: buildAuthHeaders(),
  })
  return handleResponse<RouterStatusResponse>(res)
}
