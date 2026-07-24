# DocIntel (ZETDC Internal Document AI)

DocIntel is an internal ZETDC system for uploading, summarising, analysing, and querying company documents using AI.

It consists of:
- A **FastAPI** backend (Python) exposing REST APIs and Swagger docs.
- A **React + TypeScript** frontend (Vite) providing a ZETDC‑branded web/mobile UI.
- A **React Native (Expo)** mobile app for iOS and Android.

> Stack: FastAPI, Pydantic, Uvicorn, React, TypeScript, Vite, Expo.

---

## Project Structure

- `app/` – FastAPI backend
  - `main.py` – FastAPI app entry (routes, CORS, Swagger)
  - `config.py` – environment‑based settings
  - `controllers/` – HTTP controllers (routing layer)
  - `services/` – business logic (document, chat, etc.)
  - `models/` – Pydantic models / API schemas
- `frontend/` – React + TypeScript ZETDC UI
  - `src/App.tsx` – main app component
  - `src/pages/DocumentViewPage.tsx` – analysis + copilot screen
  - `src/api/client.ts` – API client for backend
  - `src/theme/colors.ts` – ZETDC colour palette
- `mobile/` – React Native (Expo) iOS/Android app
  - `App.tsx` – mobile app entry
  - `src/screens/ChatScreen.tsx` – chat interface with EC history
  - `src/screens/DocumentUploadScreen.tsx` – document ingestion + metadata
- `run_dev.py` – helper script to start backend and frontend together (optional)
- `requirements.txt` – Python backend dependencies

---

## Prerequisites

- Python 3.12.x (Windows) installed and available via the Python Launcher (`py`)
- Node.js + npm installed, `npm` available on PATH
- Expo CLI available (`npm i -g expo-cli`) or use `npx expo`

---

## Backend Setup (FastAPI)

From the project root:

```bash
cd C:\Users\ze9167523\Documents\trae_projects\doctel
py -3.12 -m pip install -r requirements.txt
```

Environment variables (optional but recommended):

- `DOCINTEL_ENV` – environment name (default: `development`)
- `DOCINTEL_DB_URL` – database URL (for future persistent storage)
- `DOCINTEL_LLM_API_KEY` – API key for LLM provider
- `DOCINTEL_OBJECT_STORAGE_BUCKET` – documents bucket/container
- `DOCINTEL_CORS_ORIGINS` – comma‑separated list of allowed origins (default: `*`)

Example (PowerShell):

```powershell
$env:DOCINTEL_ENV = "development"
$env:DOCINTEL_CORS_ORIGINS = "http://localhost:5173"
```

---

## Frontend Setup (React + TypeScript)

```bash
cd C:\Users\ze9167523\Documents\trae_projects\doctel\frontend
npm install
```

Optional `.env` in `frontend/`:

```env
VITE_API_BASE_URL=http://localhost:8000
```

---

## Mobile App Setup (iOS / Android)

```bash
cd C:\Users\ze9167523\Documents\trae_projects\doctel\mobile
npm install
```

For a physical device, set the backend base URL to your machine’s IP:

```bash
set EXPO_PUBLIC_API_BASE_URL=http://192.168.1.20:8000
```

---

## How to Run (Recommended)

Use two terminals: one for the backend, one for the frontend.

### 1. Start Backend

```bash
cd C:\Users\ze9167523\Documents\trae_projects\doctel
py -3.12 -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload 
Or
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
python -m uvicorn app.main:app --host 10.119.239.203 --port 8000 --reload
```

Backend URLs:
- Swagger API docs: `http://localhost:8000/docs`
- OpenAPI JSON: `http://localhost:8000/openapi.json`
- Health check: `http://localhost:8000/healthz`

---

## Ollama (Local Models)

DocIntel uses Ollama locally at `http://127.0.0.1:11434` for text generation, embeddings, and vision.

Key endpoints:
- `GET /api/models/available` → returns `{ installed, available, offline, default_model, embed_model, vision_model }`
- `POST /api/models/pull` → server-sent events stream for pulling a model (resume + retry)

Troubleshooting:
- If chat returns `ollama_unreachable`, start Ollama: `ollama serve`
- If a model is not installed, pull it: `ollama pull <model>`

---

## Bootstrap Indexing (Ready on Startup)

On backend startup DocIntel scans and indexes local folders (default):
- `C:\LocalAI\data\projects\**\*`
- `C:\LocalAI\data\uploads\**\*`

Endpoints:
- `GET /api/bootstrap/status` → progress + counts
- `POST /api/admin/reindex` (admin) → trigger a rescan

Notes:
- New/changed files are detected by SHA-256 and queued for ingestion.
- Embeddings use `nomic-embed-text` via Ollama.

---

## Model Pull Progress

Endpoints:
- `POST /api/models/pull` with `{ "model": "llama3.2:3b-instruct", "resume": true }` starts a background pull.
- `GET /api/models/pull/status/{model}` returns `{ state, percent, bytes_completed, bytes_total, eta_seconds, attempt, last_event, error, resume_supported }`.

---

## Logout + Token Expiry

- `POST /auth/logout` returns `{ "success": true }` and revokes the in-memory session token.
- Protected endpoints return `401` with `{ "error": "token_expired" }` when the token is missing/expired.

---

## Admin System Settings

Admin-only endpoints:
- `GET /admin/settings` → effective settings + per-key sources (`default|file|db`)
- `PATCH /admin/settings` → apply partial updates (DB overrides) + restart recommendations
- `POST /admin/settings/test` → validate without applying
- `POST /admin/settings/backup` → write snapshot to `C:\LocalAI\backups\settings\YYYYMMDD_HHMMSS.yaml`
- `POST /admin/settings/restore` → restore from `{ path }` or `{ yaml }`
- `GET /admin/settings/audit` → audit feed

### 2. Start Frontend

```bash
cd C:\Users\ze9167523\Documents\trae_projects\doctel\frontend
npm run dev -- --host 127.0.0.1 --port 5173
```
 
Frontend URL:
- Web UI (desktop + mobile responsive): `http://localhost:5173/`

If Vite reports a different port (e.g. 5174), open the exact `Local` URL it prints.

---

## Run Mobile App

From the `mobile/` folder:

```bash
npm start
```

Then:

- Press `a` for Android emulator
- Press `i` for iOS simulator (macOS only)
- Scan the QR code with Expo Go on a device

---

## Optional: Single Dev Command

You can also use the helper script:

```bash
cd C:\Users\ze9167523\Documents\trae_projects\doctel
python run_dev.py
```

This attempts to:

- Start `npm run dev` in `frontend/`
- Start the FastAPI backend with Uvicorn

If ports are busy or `npm` is not on PATH, prefer the two‑terminal method described above.

---

## Current Features

Backend:
- Upload a document with metadata (Project Name, Document Type, Date).
- Fetch document analysis: executive + detailed summary, entities, topics, sentiment.
- Fetch suggested prompts for a document.
- Ask questions about a document via chat endpoint, with source snippets.
- Swagger UI with grouped `Documents` tag.
- Retrieve user chat history by EC number.
 - Store uploaded files on disk in `app/data/documents/` as a centralized repository.

Frontend:
- ZETDC‑branded layout with header and DocIntel shell.
- Document view page showing:
  - Analysis dashboard (executive summary, detailed summary, key insights).
  - DocIntel Copilot (suggested prompts + chat interface with citations).
- Model selector in the chat bar (persisted in browser + per chat session).
- Responsive layout:
  - Desktop: analysis on the left, copilot on the right.
  - Mobile: copilot first, analysis below, single column scroll.

Mobile:
- iOS/Android app with EC number gate.
- Document ingestion screen with metadata fields and file upload.
- Chat screen with prompts and EC history.

---

## Next Steps / Roadmap

- Integrate real document storage (database + object storage).
- Add async processing pipeline for extraction, summarisation, and analysis.
- Add vector database for document embeddings and retrieval‑augmented Q&A.
- Implement authentication and RBAC for ZETDC users.
