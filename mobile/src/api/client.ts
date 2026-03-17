import {
  DocumentCreateResponse,
  DocumentAnalysisResponse,
  PromptListResponse,
  ChatRequest,
  ChatResponse,
  ProjectCreateRequest,
  ProjectResponse,
  ProjectListResponse,
  UserHistoryResponse,
  LoginRequest,
  LoginResponse,
  EmailOtpRequest,
  EmailOtpVerifyRequest,
  EmailOtpRequestResponse,
  SummaryHistoryResponse,
} from "../types/api"
import AsyncStorage from "@react-native-async-storage/async-storage"

const BASE_URL =
  process.env.EXPO_PUBLIC_API_BASE_URL ?? "http://localhost:8000"
const AUTH_TOKEN_KEY = "docintel_auth_token"

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    if (res.status === 401) {
      await clearAuthToken()
      throw new Error("Session expired. Please sign in again.")
    }
    const text = await res.text().catch(() => "")
    throw new Error(text || res.statusText)
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

export async function chatWithDocument(
  documentId: string,
  payload: ChatRequest,
): Promise<ChatResponse> {
  const authHeaders = await buildAuthHeaders()
  const res = await fetch(`${BASE_URL}/documents/${documentId}/chat`, {
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
): Promise<UserHistoryResponse> {
  const authHeaders = await buildAuthHeaders()
  const res = await fetch(`${BASE_URL}/users/me/history`, {
    headers: authHeaders,
  })
  return handleResponse<UserHistoryResponse>(res)
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
  const res = await fetch(`${BASE_URL}/projects`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders,
    },
    body: JSON.stringify(payload),
  })
  return handleResponse<ProjectResponse>(res)
}

export async function getProjects(): Promise<ProjectListResponse> {
  const authHeaders = await buildAuthHeaders()
  const res = await fetch(`${BASE_URL}/projects`, {
    headers: authHeaders,
  })
  return handleResponse<ProjectListResponse>(res)
}
