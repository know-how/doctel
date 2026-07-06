/**
 * Shared constants for DocIntel Mobile & Frontend
 * Ensures cross-platform consistency for API endpoints, error messages, etc.
 */

export const API_ENDPOINTS = {
  // Auth
  AUTH_LOGIN: "/auth/login",
  AUTH_EMAIL_REQUEST: "/auth/email/request",
  AUTH_EMAIL_VERIFY: "/auth/email/verify",
  AUTH_LOGOUT: "/auth/logout",

  // Users
  USERS_ME: "/users/me",
  USERS_ME_HISTORY: "/users/me/history",
  USERS_ME_SUMMARY_HISTORY: "/users/me/summary-history",
  USERS_ME_DOCUMENTS: "/users/me/documents",

  // Documents
  DOCUMENTS: "/documents",
  DOCUMENTS_ANALYSIS: (id: string) => `/documents/${id}/analysis`,
  DOCUMENTS_PROMPTS: (id: string) => `/documents/${id}/prompts`,
  DOCUMENTS_CHAT: (id: string) => `/api/ask/${id}`,

  // Projects
  PROJECTS: "/projects",
  PROJECTS_ANALYSIS: (id: string) => `/projects/${id}/analysis`,

  // Sessions
  SESSIONS: "/sessions",
  SESSIONS_MESSAGES: (id: string) => `/sessions/${id}/messages`,

  // Models
  MODELS_AVAILABLE: "/api/models/available",
  MODELS_PULL: "/api/models/pull",
  MODELS_PULL_STATUS: (model: string) => `/api/models/pull/status/${encodeURIComponent(model)}`,

  // Admin
  ADMIN_SETTINGS: "/admin/settings",
  ADMIN_SETTINGS_PATCH: "/admin/settings",
  ADMIN_SETTINGS_AUDIT: "/admin/settings/audit",

  // Bootstrap
  BOOTSTRAP_STATUS: "/api/bootstrap/status",

  // Ingest
  INGEST_STATUS: "/api/ingest/status",

  // Training
  TRAINING_EXPORT: "/api/training/export-from-projects",
  TRAINING_TRAIN_ALL: "/api/training/train-all-models",
  TRAINING_FROM_PROJECTS: "/api/training/train-from-projects",
}

export const AUTH_TOKEN_KEY = "docintel_auth_token"

export const ERROR_MESSAGES = {
  SESSION_EXPIRED: "Session expired. Please sign in again.",
  ACCESS_DENIED: "Access denied. Please request access or contact the admin.",
  NETWORK_ERROR: "Network error. Please check your connection.",
  INVALID_FILE: "Invalid file type. Please upload a PDF, DOCX, or image.",
  FILE_TOO_LARGE: "File too large. Maximum size is 64MB.",
}

export const VALIDATION = {
  ZETDC_EMAIL_DOMAIN: "@zetdc.co.zw",
  MIN_PASSWORD_LENGTH: 6,
  MAX_FILE_SIZE_MB: 64,
}

export const POLLING = {
  INGEST_POLL_MS: 1500,
  MODEL_PULL_POLL_MS: 2000,
  BOOTSTRAP_POLL_MS: 3000,
}
