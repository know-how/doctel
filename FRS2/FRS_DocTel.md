# Functional Requirements Specification (FRS)
## DocTel – ZETDC Document Intelligence Platform
**Version:** 1.0  
**Date:** May 2026  
**Organisation:** Zimbabwe Electricity Transmission and Distribution Company (ZETDC)  
**Classification:** Internal Use Only

---

## 1. Introduction

### 1.1 Purpose
This document defines the functional requirements for **DocTel** (also referred to as *ZETDC DocIntel*), a privacy-first, AI-powered document intelligence platform deployed internally at ZETDC. It serves as the authoritative reference for developers, testers, and stakeholders.

### 1.2 Scope
DocTel enables ZETDC staff to upload, index, analyse, and chat with company documents using local and cloud AI models. The system comprises:
- A **FastAPI** Python backend
- A **React/TypeScript** web frontend (Vite)
- A **React Native (Expo)** mobile application (iOS & Android)
- A **ChromaDB** vector store and **SQLite** relational database
- Local AI inference via **Ollama** and optional **Google Gemini API**

### 1.3 Definitions
| Term | Meaning |
|---|---|
| Repository | A named project grouping related documents |
| Document | An uploaded file (PDF, DOCX, TXT, image) |
| Chunk | A text segment extracted from a document for vector indexing |
| RAG | Retrieval-Augmented Generation – grounding answers in retrieved chunks |
| Ingestion | The pipeline converting a raw upload into indexed, searchable content |
| EC Number | ZETDC employee identifier used for authentication |
| LoRA Adapter | Fine-tuned local model adapter produced by the Training Room |

---

## 2. User Roles & Access Control

### FR-RBAC-01 – Role Definitions
The system shall support three roles:
- **Admin** – full system access including settings, user management, and model administration
- **Analyst** – can create repositories, upload documents, and use all analysis features
- **Viewer** – read-only access to repositories and chat within shared documents

### FR-RBAC-02 – Role Enforcement
Every API endpoint shall enforce role-based access. Attempting an unauthorised action shall return HTTP 403.

### FR-RBAC-03 – Project Membership
A user may belong to multiple repositories with individual roles (`owner`, `analyst`, `viewer`). Admins have access to all repositories.

---

## 3. Authentication

### FR-AUTH-01 – Email OTP Login
The system shall authenticate users via a one-time password (OTP) sent to a `@zetdc.co.zw` email address. OTP validity shall be time-limited.

### FR-AUTH-02 – EC Number / Password Login
The system shall support EC number and password authentication via the ZETDC Active Directory (LDAP/LDAPS), configurable via `DOCINTEL_AD_URL` and related environment variables.

### FR-AUTH-03 – Session Tokens
Upon successful login the system shall issue a Bearer token (default 30-minute expiry). A refresh token (default 7-day expiry) shall allow silent renewal.

### FR-AUTH-04 – Token Revocation
`POST /auth/logout` shall immediately invalidate the active session token.

### FR-AUTH-05 – Expired Token Handling
Protected endpoints shall return HTTP 401 with `{"error": "token_expired"}` on expired or missing tokens. The frontend shall automatically prompt re-authentication.

---

## 4. Document Management

### FR-DOC-01 – File Upload
Users with the Analyst role shall be able to upload documents of the following types: PDF, DOCX, TXT, PNG, JPEG, WEBP, GIF, BMP. Maximum file size is 64 MB per file. Multi-file uploads shall be supported in a single request.

### FR-DOC-02 – Document Metadata
At upload time users may optionally supply: Repository assignment, Document Type, Document Date, and Tags.

### FR-DOC-03 – SHA-256 Deduplication
The system shall compute a SHA-256 hash of each uploaded file. Files already present in the repository (by hash) shall not be re-indexed unless a retry is explicitly requested.

### FR-DOC-04 – Document Library
The system shall provide a searchable, filterable library of all documents accessible to the current user, showing filename, repository, status, and date.

### FR-DOC-05 – Document Download
Users shall be able to download the original uploaded file from the document library.

### FR-DOC-06 – Document Deletion
Admin and the uploading Analyst may delete a document. Deletion shall remove the file, all chunks, embeddings, analysis records, and suggested prompts.

### FR-DOC-07 – Document Tagging
Documents shall support free-text tags. Tags shall be searchable and filterable in the library.

### FR-DOC-08 – Auto Project Assignment
The ingestion pipeline shall attempt to automatically assign uploaded documents to an existing repository based on filename/content similarity, providing a confidence score. Documents below the confidence threshold shall be flagged for manual review.

---

## 5. Document Ingestion Pipeline

### FR-ING-01 – Ingestion Stages
Upon upload, each document shall pass through the following stages in sequence:
1. `uploaded` – file saved to disk
2. `extract` – raw text extraction
3. `chunk` – text split into overlapping segments
4. `embed` – vector embeddings generated per chunk
5. `analyse` – executive summary, entities, topics generated
6. `prompts` – suggested questions generated
7. `done` / `completed` – document fully ready for chat

### FR-ING-02 – Text Extraction
- **PDF:** extracted via `pypdf` (page-by-page)
- **DOCX:** extracted via `python-docx`
- **TXT:** read directly
- **Images (PNG/JPG/WEBP/GIF/BMP):** OCR via Gemini Vision API; fallback message if API unavailable

### FR-ING-03 – Chunking
Text shall be split into overlapping chunks. Default chunk size is 1 000 characters with 150-character overlap, configurable via environment variables.

### FR-ING-04 – Embedding
Chunks shall be embedded using the configured embedding model (default: `nomic-embed-text` via Ollama) and stored in ChromaDB keyed by project and document ID.

### FR-ING-05 – Ingest Status Streaming
The system shall expose a Server-Sent Events (SSE) endpoint (`GET /api/ingest/stream?document_id=…`) that streams real-time ingestion progress to the frontend.

### FR-ING-06 – Ingest Status Polling
A polling endpoint (`GET /api/ingest/status?document_id=…`) shall return the current ingestion step, percentage, and any error message.

### FR-ING-07 – Ingest Retry
Users may trigger re-ingestion of a failed document via `POST /api/ingest/retry`. All prior chunks, embeddings, and analysis records shall be cleared before re-running.

### FR-ING-08 – Bootstrap Indexing
On startup the system shall scan configured local folders (e.g. `C:\LocalAI\data\projects`) and queue any new or changed files for ingestion. Progress is reported via `GET /api/bootstrap/status`.

---

## 6. Document Analysis

### FR-ANA-01 – Automatic Analysis
After ingestion the system shall generate and persist the following analysis for each document:
- Executive summary (narrative prose, no markdown bullets)
- Detailed summary (sentence-level findings by theme)
- Sentiment classification: Positive / Neutral / Negative / Urgent
- Named entities (people, organisations, dates, locations)
- Key topics (short keywords)
- Action items (sentences containing obligation language)
- Decisions (sentences containing approval/resolution language)

### FR-ANA-02 – Analysis API
Analysis shall be retrievable via `GET /api/documents/{id}/analysis`.

### FR-ANA-03 – Suggested Prompts
The system shall generate 3–5 contextual suggested questions per document and expose them via `GET /api/prompts/suggest?document_id=…`.

### FR-ANA-04 – Analysis Display
The web frontend shall display the analysis in a split-panel layout: analysis on the left, AI copilot on the right (desktop); stacked single column on mobile.

---

## 7. AI Chat (RAG Copilot)

### FR-CHAT-01 – Document-Scoped Chat
Users shall be able to ask natural language questions about a specific document. Answers shall be grounded in that document's chunks via RAG. Each answer shall include inline source citations (`[Doc: <filename>, chunk <n>]`).

### FR-CHAT-02 – Repository-Scoped Chat
Users may broaden the search scope to all documents within a repository (scope: `project`), retrieving and merging the top-k most relevant chunks across all documents.

### FR-CHAT-03 – Organisation-Wide Chat
Users may query across all repositories they have access to (scope: `all`).

### FR-CHAT-04 – Global / General Chat
When no document is selected the system shall answer using the full organisational knowledge base and optionally fall back through the 4-tier model router.

### FR-CHAT-05 – Chat Sessions
Each chat interaction shall be tied to a persistent session (UUID). Sessions shall store model, scope, title (derived from first message), and timestamps. Sessions shall be retrievable for history review.

### FR-CHAT-06 – Message Persistence
All user and assistant messages shall be persisted in the database with role, content, status (`pending|done|failed`), and citations JSON.

### FR-CHAT-07 – Concurrent Request Guard
The system shall prevent duplicate simultaneous submissions for the same session/document pair, returning HTTP 409 if a request is already in flight.

### FR-CHAT-08 – Stale Document Recovery
If a chat request references a document ID that no longer exists the backend shall return `{"error": "document_not_found"}` (HTTP 404). The frontend shall clear the cached session, reset the active document, and display a user-friendly recovery message.

### FR-CHAT-09 – Reference Document Pinning
Users may pin one or more reference documents in the chat toolbar. The selected filenames are prepended to the question context as `[Referencing: <filename>]`.

### FR-CHAT-10 – Chat While Ingesting
The system shall optionally allow chat while a document is still ingesting (configurable: `allow_chat_while_ingesting`). If disabled, a 202 response shall be returned with a retry-after delay.

---

## 8. AI Model Management

### FR-MODEL-01 – 4-Tier Model Router
The system shall route inference requests through four tiers in priority order:
1. **Tier 1 – Local LoRA adapter** (fastest, fully private; used if an active adapter exists and produces a confident answer)
2. **Tier 2 – Ollama** (primary local model, RAM-aware automatic switching between 8B and 3B variants)
3. **Tier 2b – Gemini API** (cloud; used if configured and Ollama is unavailable or low-confidence)
4. **Tier 3 – Cloud Teacher** (configurable external LLM for difficult queries)
5. **Tier 4 – Web Search** (DuckDuckGo fallback, last resort)

### FR-MODEL-02 – RAM-Aware Model Selection
When automatic switching is enabled the system shall select models based on available free RAM:
- ≥ 7 000 MB: Qwen 9B (if enabled)
- ≥ 6 000 MB: LLaMA 8B
- < 6 000 MB: LLaMA 3B fallback

### FR-MODEL-03 – Model Pull
Admin users may pull new Ollama models via `POST /api/models/pull`. Progress (percent, ETA, bytes) shall be streamed and resumable across retries.

### FR-MODEL-04 – Model Selector UI
The web and mobile interfaces shall display a model selector allowing users to switch the active generation model per session. The preference shall be persisted in the browser.

### FR-MODEL-05 – Available Models API
`GET /api/models/available` shall return: installed models, all available models, offline flag, default model, embed model, and vision model.

### FR-MODEL-06 – Model Labels
Admin may assign human-readable labels to model IDs, exposed via `GET /api/models/labels`.

---

## 9. Diagram & Chart Generation

### FR-DIAG-01 – Mermaid Flowchart Generation
Users shall be able to request a process flow diagram based on document content or free-text description. The system shall return a Mermaid diagram code block renderable in the chat panel.

### FR-DIAG-02 – Chart Builder
Users may upload a CSV file. The system shall analyse column types and suggest chart configurations. Users select X/Y axes and chart type; the system generates and returns a chart image URL embedded in the chat.

### FR-DIAG-03 – Policy & Draft Generation
When `force_policy=true` is passed the AI copilot shall produce a structured policy draft with standard ZETDC sections: Purpose, Scope, Definitions, Responsibilities, Procedures, Exceptions, Version Control, References.

---

## 10. Document Analysis Toolbox (Analyse Tab)

### FR-TOOL-01 – Multi-Document Summarisation
Users may select multiple documents and request batch summaries. The system shall return an executive summary and topics for each document.

### FR-TOOL-02 – Data Extraction
Users may provide a JSON schema; the system shall extract matching fields from each selected document and return structured results.

### FR-TOOL-03 – Document Comparison
Users may select two documents for side-by-side comparison. The system shall identify similarities, differences, and conflicting content.

### FR-TOOL-04 – Document Classification
Users may define classification rules; the system shall apply them across selected documents and return tags/labels with confidence scores.

### FR-TOOL-05 – Analyse Chat
Users may open a multi-document chat session where the context is scoped to the selected document set.

---

## 11. Collaboration

### FR-COLLAB-01 – Team Member Management
Admin users shall be able to view all registered users, update roles (admin/analyst/viewer), and remove users.

### FR-COLLAB-02 – Project Membership
Repository owners and admins may add or remove members from a repository and assign per-repository roles.

### FR-COLLAB-03 – Activity Feed
The system shall maintain and expose an activity log showing recent document uploads, analysis completions, and chat sessions.

### FR-COLLAB-04 – Shared Documents
Users shall be able to share document views or chat sessions with team members.

---

## 12. Outputs & Exports

### FR-OUT-01 – Output History
The system shall store AI-generated outputs (summaries, extractions, reports) and make them retrievable via `GET /api/outputs`.

### FR-OUT-02 – Export Formats
Users shall be able to export outputs in PDF, DOCX, or JSON format via `GET /api/outputs/{id}/export?format=…`.

### FR-OUT-03 – Reports Page
The frontend shall provide a reports view displaying generated outputs with filtering by type and date.

---

## 13. Training Room

### FR-TRAIN-01 – LoRA Fine-Tuning
Admin users shall be able to trigger LoRA fine-tuning of the base language model using accumulated ZETDC-specific Q&A pairs. Training shall run in a background thread without blocking the API.

### FR-TRAIN-02 – Training Triggers
Training may be triggered in three modes:
- **Immediate** (`train_now`) – starts at once
- **Idle** (`train_idle`) – starts only when free RAM exceeds the configured threshold
- **Batch** (`train_batch`) – processes a specific inbox folder first, then trains

### FR-TRAIN-03 – Training Progress
`GET /api/training/status` shall return current job state, progress fraction, message, and timestamps.

### FR-TRAIN-04 – Training History
`GET /api/training/history` shall return a list of past training runs with adapter IDs, sample counts, and step counts.

### FR-TRAIN-05 – Adapter Registry
Each successful training run shall register a versioned LoRA adapter. The most recent adapter shall be automatically promoted as the active Tier-1 model.

### FR-TRAIN-06 – Teacher Sample Capture
When the cloud teacher model (Tier 3) is used, the system shall optionally capture the prompt/response pair as a training sample for future fine-tuning.

### FR-TRAIN-07 – Training Room UI
The web frontend shall provide a Training Room page showing inbox file count, job status, adapter history, and trigger buttons.

---

## 14. Admin Settings

### FR-ADMIN-01 – Settings Management
Admin users shall be able to view, edit, and persist all system settings via `GET/PATCH /admin/settings`. Changes shall be applied at runtime where possible; restart-required changes shall be flagged.

### FR-ADMIN-02 – Settings Sources
Each setting shall indicate its source: `default`, `file` (config.yaml), or `db` (database override).

### FR-ADMIN-03 – Settings Validation
`POST /admin/settings/test` shall validate a proposed settings payload without applying it.

### FR-ADMIN-04 – Settings Backup & Restore
Admin may back up settings to a timestamped YAML file and restore from a file path or inline YAML.

### FR-ADMIN-05 – Settings Audit Log
All settings changes shall be logged with the changed key, old value, new value, user, and timestamp. Retrievable via `GET /admin/settings/audit`.

### FR-ADMIN-06 – Prompt Management
Admin may create, edit, and delete system prompt templates used across different task types (`GET/POST /admin/prompts`).

### FR-ADMIN-07 – Context Token Management
Admin may configure maximum context token windows per task type.

### FR-ADMIN-08 – Integration Settings
Admin may configure integrations (email server, AD, external APIs) via `PATCH /admin/integrations`.

---

## 15. Processing Status

### FR-PROC-01 – System Status Dashboard
The frontend shall provide a Processing Status page showing all documents currently ingesting, their step, percent complete, and any errors.

### FR-PROC-02 – Health Check
`GET /healthz` shall return a lightweight health response indicating the backend is running.

---

## 16. Mobile Application

### FR-MOB-01 – Feature Parity
The React Native mobile app shall provide feature parity with the web frontend for core workflows: login, document upload, document library, chat, analysis viewing, and settings.

### FR-MOB-02 – Document Upload (Mobile)
Users shall be able to upload documents from device storage with metadata (repository, type, date) via the mobile app.

### FR-MOB-03 – Chat (Mobile)
The mobile chat screen shall support document-scoped and global chat with model selection, suggested prompts, and citation display.

### FR-MOB-04 – Analyse Tools (Mobile)
The mobile app shall expose summarisation, extraction, comparison, and classification screens.

### FR-MOB-05 – Admin Screens (Mobile)
Admin users on mobile shall have access to model management and prompt management screens.

### FR-MOB-06 – Offline Awareness
The mobile app shall detect when the backend is unreachable and display an appropriate offline message.

---

## 17. Security Requirements

### FR-SEC-01 – Transport Security
In production the system shall support HTTPS. The `security.use_local_https` flag controls local certificate use.

### FR-SEC-02 – Database Encryption
SQLite storage shall support encryption when `security.encrypt_sqlite` is enabled.

### FR-SEC-03 – Windows EFS
On Windows hosts the data directory shall optionally use Windows Encrypting File System (EFS) when `security.use_windows_efs` is enabled.

### FR-SEC-04 – CORS
CORS origins shall be explicitly configured. The default development value of `*` must be restricted in production.

### FR-SEC-05 – Email Domain Restriction
OTP login shall only accept addresses matching the configured allowed email domain (default: `@zetdc.co.zw`).

### FR-SEC-06 – No External Data Leakage (Offline Mode)
When `offline_only=true` no document content shall be sent to any external service. Gemini API and cloud teacher calls shall be disabled.

---

## 18. Performance Requirements

### FR-PERF-01 – Ingestion Speed
A 10-page PDF shall complete full ingestion (extract → embed → analyse) within 15 seconds on the reference hardware.

### FR-PERF-02 – Chat Latency
First-token response for a RAG query shall begin streaming within 3 seconds under normal load.

### FR-PERF-03 – Ingest Poll Interval
The frontend shall poll ingestion status no more frequently than every 1 500 ms (configurable).

---

## 19. API Summary

| Category | Method | Endpoint | Description |
|---|---|---|---|
| Auth | POST | `/auth/email/request` | Request OTP |
| Auth | POST | `/auth/email/verify` | Verify OTP, get token |
| Auth | POST | `/auth/logout` | Revoke session |
| Documents | POST | `/api/upload` | Upload document(s) |
| Documents | GET | `/api/documents` | List documents |
| Documents | DELETE | `/api/documents/{id}` | Delete document |
| Documents | GET | `/api/documents/{id}/analysis` | Get analysis |
| Ingest | GET | `/api/ingest/status` | Poll ingest status |
| Ingest | GET | `/api/ingest/stream` | SSE ingest stream |
| Ingest | POST | `/api/ingest/retry` | Retry failed ingest |
| Chat | POST | `/api/ask/{document_id}` | Document chat |
| Chat | POST | `/api/ask` | Global chat |
| Chat | POST | `/api/chat/sessions` | Create session |
| Chat | GET | `/api/chat/sessions/{id}/messages` | Get messages |
| Models | GET | `/api/models/available` | List models |
| Models | POST | `/api/models/pull` | Pull Ollama model |
| Projects | POST | `/api/projects` | Create repository |
| Projects | GET | `/api/projects` | List repositories |
| Projects | DELETE | `/api/projects/{id}` | Delete repository |
| Training | POST | `/api/training/start` | Start training |
| Training | GET | `/api/training/status` | Training status |
| Admin | GET | `/admin/settings` | Get settings |
| Admin | PATCH | `/admin/settings` | Update settings |
| Admin | GET | `/admin/settings/audit` | Audit log |
| Outputs | GET | `/api/outputs` | List outputs |
| Outputs | GET | `/api/outputs/{id}/export` | Export output |

---

## 20. Data Model Summary

| Entity | Key Fields |
|---|---|
| User | id, username, ec_number, email, display_name, role |
| Project | id, name, owner_user_id |
| ProjectMember | project_id, user_id, role_in_project |
| Document | id, project_id, filename, path, sha256, status, ingest_step, ingest_percent |
| DocAnalysis | document_id, executive_summary, detailed_summary, sentiment, entities_json, topics_json |
| Chunk | document_id, project_id, chunk_index, text, embedding_id |
| Embedding | id, vector_ref (ChromaDB ID) |
| Session | id, session_uuid, project_id, document_id, user_id, model_name, scope, title |
| Message | session_id, role, content, status, citations_json |
| SuggestedPrompt | document_id, prompt_text |
| Diagram | project_id, session_id, title, mermaid, drawing_prompt |
| SystemSetting | key, value_json, updated_by_user_id |
| SettingsAudit | key, old_value_json, new_value_json, changed_by_user_id, changed_at |

---

## 21. Use Case Diagram

See **[UseCaseDiagram.md](./UseCaseDiagram.md)** for the full use case diagram covering all 50 use cases across 6 actors (Viewer, Analyst, Admin, Ollama, Gemini API, Active Directory).

---

*End of Document*
