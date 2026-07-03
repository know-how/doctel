# 🔌 Mobile API Quick Reference

**Updated:** April 17, 2026  
**Version:** 1.0.0  

---

## 📍 API Base URL

```typescript
const BASE_URL = process.env.EXPO_PUBLIC_API_BASE_URL ?? "http://172.16.4.60:8000"
```

---

## 🔐 Authentication

### Login Methods
| Method | Endpoint | Parameters | Returns |
|--------|----------|-----------|---------|
| EC + Password | `POST /auth/login` | `{ec_number, password}` | `{access_token, ec_number}` |
| Email OTP Request | `POST /auth/email/request` | `{email}` | `{message}` |
| Email OTP Verify | `POST /auth/email/verify` | `{email, code}` | `{access_token, ec_number}` |
| Get Current User | `GET /users/me` | None | `{email, ec_number, ...}` |
| Logout | `POST /auth/logout` | None | `{success: boolean}` |

### Usage
```typescript
import { login, requestEmailOtp, verifyEmailOtp, getMe, logout } from "./api/client"

// EC login
const res = await login({ ec_number: "EC12345", password: "pwd123" })
await setAuthToken(res.access_token)

// Email login
await requestEmailOtp({ email: "user@zetdc.co.zw" })
const res = await verifyEmailOtp({ email: "user@zetdc.co.zw", code: "123456" })
await setAuthToken(res.access_token)

// Get current user
const user = await getMe()

// Logout
await logout()
```

---

## 📄 Documents

| Method | Endpoint | Parameters | Returns | Status |
|--------|----------|-----------|---------|--------|
| Upload | `POST /documents` | `FormData{file, project_id?, ...}` | `DocumentCreateResponse` | ✅ Works |
| Get My Docs | `GET /api/me/documents` | None | `{documents: []}` | ✅ Fixed |
| Get Analysis | `GET /documents/{id}/analysis` | `{id}` | `DocumentAnalysisResponse` | ✅ Works |
| Get Prompts | `GET /documents/{id}/prompts` | `{id}` | `PromptListResponse` | ✅ Works |
| Download File | `GET /documents/{id}/file` | `{id}` | `Blob` | ✅ Works |
| Download (API) | `GET /api/documents/{id}/download` | `{id}` | `Blob` | ✅ Works |
| Move to Project | `PUT /api/documents/{id}/project` | `{id, project_id}` | `{ok: boolean}` | ✅ Works |
| Retry Ingest | `POST /api/ingest/retry` | `?document_id={id}` | `{ok: boolean}` | ✅ Fixed |

### Usage
```typescript
import { 
  uploadDocument, getMyDocuments, getDocumentAnalysis, 
  getDocumentPrompts, downloadDocumentFile, downloadDocumentFileApi,
  overrideDocumentProjectAPI, retryIngest, getIngestStatus
} from "./api/client"

// Upload document
const res = await uploadDocument(fileUri, fileName, mimeType, {
  project_id: "proj_123",
  document_type: "Memo",
  document_date: "2026-04-17"
})

// Get user documents
const docs = await getMyDocuments()

// Get analysis
const analysis = await getDocumentAnalysis("doc_123")

// Get suggested prompts
const prompts = await getDocumentPrompts("doc_123")

// Download files
const blob1 = await downloadDocumentFile("doc_123")
const blob2 = await downloadDocumentFileApi("doc_123")

// Move document
await overrideDocumentProjectAPI("doc_123", "proj_456")

// Retry ingestion
await retryIngest("doc_123")
```

---

## 💬 Chat & Sessions

| Method | Endpoint | Parameters | Returns | Status |
|--------|----------|-----------|---------|--------|
| Chat w/ Doc | `POST /api/ask/{id}` | `{id, question, ...}` | `ChatResponse` | ✅ Works |
| Global Chat | `POST /api/ask` | `{question, model, ...}` | `ChatResponse` | ✅ Fixed |
| Create Session | `POST /api/chat/sessions` | `{document_id?, scope?}` | `{session_id}` | ✅ Fixed |
| List Sessions | `GET /api/chat/sessions` | `?project_id=X&limit=50` | `{sessions: []}` | ✅ Fixed |
| Get Messages | `GET /api/chat/sessions/{id}/messages` | `{id, ?limit=100}` | `ChatMessagesResponse` | ✅ New |
| Set Model | `POST /api/chat/sessions/{id}/model` | `{id, model}` | `{ok, session_id, model}` | ✅ New |
| Update Session | `PATCH /api/chat/sessions/{id}` | `{id, title?, model?}` | `{ok: boolean}` | ✅ New |
| Delete Session | `DELETE /api/chat/sessions/{id}` | `{id}` | `{ok: boolean}` | ✅ New |

### Usage
```typescript
import {
  chatWithDocument, chatGlobally, createChatSession,
  getChatSessions, getChatMessages, setChatSessionModel,
  patchChatSession, deleteChatSession
} from "./api/client"

// Chat with document
const res = await chatWithDocument("doc_123", {
  question: "What is the main topic?",
  session_id: "sess_456"
})

// Global chat
const res = await chatGlobally({
  question: "Find all budgets",
  model: "llama2"
})

// Session management
const session = await createChatSession("doc_123", "document")
const sessions = await getChatSessions()
const messages = await getChatMessages("sess_123")

// Model selection
await setChatSessionModel("sess_123", "llama3")

// Session updates
await patchChatSession("sess_123", { title: "Budget Analysis" })

// Delete session
await deleteChatSession("sess_123")
```

---

## 🤖 Models

| Method | Endpoint | Parameters | Returns | Status |
|--------|----------|-----------|---------|--------|
| Available | `GET /api/models/available` | None | `{models: []}` | ✅ Works |
| Get Labels | `GET /api/models/labels` | None | `{labels: {...}}` | ✅ Works |
| Pull Model | `POST /api/models/pull` | `{model, resume?}` | `ModelPullStatusResponse` | ✅ Works |
| Pull Status | `GET /api/models/pull/status/{model}` | `{model}` | `ModelPullStatusResponse` | ✅ Works |

### Usage
```typescript
import {
  getAvailableModels, getModelLabels, 
  startModelPull, getModelPullStatus
} from "./api/client"

// Get available models
const models = await getAvailableModels()

// Get model descriptions
const labels = await getModelLabels()

// Pull a new model
const status = await startModelPull("llama3", true)

// Check pull status
const pullStatus = await getModelPullStatus("llama3")
console.log(pullStatus.progress) // 0-100%
console.log(pullStatus.status)   // "downloading" | "completed" | "failed"
```

---

## 📁 Projects

| Method | Endpoint | Parameters | Returns | Status |
|--------|----------|-----------|---------|--------|
| Create | `POST /projects` | `{name}` | `ProjectResponse` | ✅ Works |
| List | `GET /projects` | None | `{projects: []}` | ✅ Works |
| Get Details | `GET /projects/{id}` | `{id}` | `ProjectResponse` | ✅ Works |
| Get My Projects | `GET /api/me/projects` | None | `{projects: []}` | ✅ Works |
| Get Analysis | `GET /projects/{id}/analysis` | `{id}` | `DocumentAnalysisResponse` | ✅ Works |

### Usage
```typescript
import {
  createProject, getProjects, getProjectAnalysis, getMyProjects
} from "./api/client"

// Create project
const proj = await createProject({ name: "Q1 Budget" })

// List all projects
const all = await getProjects()

// Get my projects
const my = await getMyProjects()

// Get project analysis
const analysis = await getProjectAnalysis("proj_123")
```

---

## 🔧 System & Utilities

| Method | Endpoint | Parameters | Returns | Status |
|--------|----------|-----------|---------|--------|
| Bootstrap Status | `GET /api/bootstrap/status` | None | `BootstrapStatusResponse` | ✅ Works |
| Ingest Status | `GET /api/ingest/status` | `?document_id={id}` | `IngestStatusResponse` | ✅ Works |
| Suggest Prompts | `GET /api/prompts/suggest` | `?document_id={id}` | `{prompts: [...]}` | ✅ Fixed |
| Generate Flowchart | `POST /api/flowchart/generate` | `{text, diagram_type?, model?}` | `{mermaid, drawing_prompt}` | ✅ Fixed |
| UI Settings | `GET /api/settings/ui` | None | `{...}` | ✅ Fixed |

### Usage
```typescript
import {
  getBootstrapStatus, getIngestStatus, 
  suggestPrompts, flowchartGenerate, getUiSettings
} from "./api/client"

// Check bootstrap
const bootstrap = await getBootstrapStatus()
console.log(bootstrap.status) // "completed" | "pending"

// Check ingest
const ingest = await getIngestStatus("doc_123")
console.log(ingest.status)    // "completed" | "pending" | "failed"

// Get suggested prompts
const suggestions = await suggestPrompts("doc_123")

// Generate diagram
const diagram = await flowchartGenerate({
  text: "Create a flowchart for the process",
  model: "gpt-4"
})

// Get UI settings
const settings = await getUiSettings()
```

---

## 🧪 API Verification Tests

```typescript
import { runApiVerification, printTestResults } from "./api/verification"

// Run all tests
const results = await runApiVerification()
printTestResults(results)

// Check specific results
results.results.forEach(test => {
  console.log(`${test.name}: ${test.status}`)
  if (test.status === "fail") {
    console.log(`  Error: ${test.error}`)
  }
})
```

---

## 🔄 Response Types Reference

### ChatResponse (Union Type)
```typescript
// Success Response
{
  answer: string
  citations: Array<{ filename, chunk_index, text }>
  cross_references?: Array<{ filename, reason }>
  used_model: string
  session_id: string
}

// Queued Response
{
  status: "queued" | "pending_analysis"
  reason: string
  document_status: string
  retry_after_ms: number
  poll_url: string
  session_id: string
  pending_message_id?: number
}
```

### DocumentAnalysisResponse
```typescript
{
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
```

### Bootstrap Status Response
```typescript
{
  status: "completed" | "pending"
  message?: string
  progress?: number // 0-100
  models_loaded?: boolean
  rag_ready?: boolean
}
```

---

## 🛠️ Common Patterns

### Error Handling
```typescript
try {
  const result = await getMyDocuments()
} catch (error) {
  if (error instanceof ApiError) {
    console.error(`API Error [${error.status}]: ${error.message}`)
    if (error.status === 401) {
      // Token expired, redirect to login
    }
  } else {
    console.error("Network or unknown error:", error)
  }
}
```

### Auth Header Management
```typescript
// Token is automatically included in all authenticated requests
// via buildAuthHeaders() function

// Manual token management
await setAuthToken(token)     // Save token
const token = await getAuthToken()  // Retrieve token
await clearAuthToken()        // Delete token
```

### Polling Pattern
```typescript
// Poll for status updates
let attempts = 0
const checkStatus = async () => {
  const status = await getIngestStatus("doc_123")
  if (status.status === "completed") {
    console.log("Complete!")
  } else if (attempts < 60) {
    attempts++
    setTimeout(checkStatus, 1000) // Check every second
  }
}
```

---

## 📚 Related Files

- **Implementation:** `mobile/src/api/client.ts`
- **Verification:** `mobile/src/api/verification.ts`
- **Types:** `mobile/src/types/api.ts`
- **Documentation:** `MOBILE_ALIGNMENT_COMPLETE.md`

---

## 🔗 Endpoint Status Legend

- ✅ **Works** - Verified working with mobile app
- 🔧 **Fixed** - Recently corrected from incorrect route
- ⚠️ **Pending** - UI not yet implemented (API ready)
- ❌ **Not Available** - Not supported on mobile

---

**Last Updated:** April 17, 2026  
**All Endpoints:** 33+ verified ✅  
**Production Ready:** Yes ✅
