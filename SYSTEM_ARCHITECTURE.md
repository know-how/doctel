# DocTel — System Architecture & Documentation

> **Internal AI System for ZETDC (Zimbabwe Electricity Transmission and Distribution Company)**  
> *Version: 1.0.0 | Last updated: 2026-06-24*

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Technology Stack](#2-technology-stack)
3. [Project Structure](#3-project-structure)
4. [Architecture & Data Flow](#4-architecture--data-flow)
5. [Backend Components](#5-backend-components)
6. [Database Schema](#6-database-schema)
7. [AI / ML Pipeline](#7-ai--ml-pipeline)
8. [Model Routing (4-Tier)](#8-model-routing-4-tier)
9. [Authentication & Authorization](#9-authentication--authorization)
10. [Frontend (Web)](#10-frontend-web)
11. [Mobile App](#11-mobile-app)
12. [Configuration Reference](#12-configuration-reference)
13. [API Endpoints](#13-api-endpoints)
14. [Deployment & Running](#14-deployment--running)

---

## 1. System Overview

**DocTel** (also referred to in the codebase as **DocIntel**) is an internal document AI platform built for ZETDC. It enables employees to:

- **Upload** documents (PDF, DOCX, images) for AI-powered analysis
- **Summarize** and **analyze** document content with structured outputs (executive summaries, entities, topics, sentiment, action items, decisions)
- **Query** documents using natural language via RAG (Retrieval-Augmented Generation)
- **Organize** documents into projects with role-based access control
- **Chat** with an AI assistant that has context from uploaded documents
- **Train** custom LoRA/QLoRA adapters on organizational documents
- **Distill** knowledge from cloud teacher models into local models

### Identity & Naming

- **System Name:** DocTel (Large Language Model for ZETDC)
- **Organization:** Zimbabwe Electricity Transmission and Distribution Company (ZETDC)
- **Codebase Name:** `DocIntel` (internal project name used in code)
- **Brand/Display Name:** DocTel

---

## 2. Technology Stack

### Backend

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Framework | **FastAPI** (Python 3.12) | REST API server |
| ASGI Server | **Uvicorn** | Production-grade ASGI |
| Validation | **Pydantic v2** | Request/response schemas |
| ORM | **SQLAlchemy** (async) | Database access |
| Database | **SQLite** (via aiosqlite) | Relational storage |
| Vector Store | **ChromaDB** | Embedding storage & similarity search |
| Config | **PyYAML** + env vars | Application configuration |
| Auth | **LDAP3** + Email OTP | Authentication (AD & email) |
| OCR | **Tesseract** + **Pillow** | Image text extraction |
| File Parsing | **PyPDF2**, **python-docx**, **pypdfium2** | Document parsing |
| ML/AI | **transformers**, **peft**, **datasets**, **torch**, **accelerate** | LoRA/QLoRA training |
| Local LLM | **llama-cpp-python**, **Ollama** | Local model inference |
| Search | **duckduckgo-search** | Web search fallback |

### Frontend (Web)

| Layer | Technology |
|-------|-----------|
| Framework | **React 18** |
| Language | **TypeScript 5** |
| Bundler | **Vite 5** |
| SWC Compiler | **@vitejs/plugin-react-swc** |

### Mobile

| Layer | Technology |
|-------|-----------|
| Framework | **React Native 0.81** |
| Platform | **Expo SDK 54** |
| Language | **TypeScript 5** |
| Build | **EAS Build** (Android) |

---

## 3. Project Structure

```
doctel/
├── app/                          # FastAPI backend
│   ├── main.py                   # App entry point, routes, middleware
│   ├── config.py                 # Pydantic settings (env + YAML)
│   ├── config.yaml               # YAML configuration
│   ├── schemas.py                # API Pydantic models
│   ├── controllers/              # HTTP routing layer
│   │   ├── auth_controller.py    #   Auth endpoints
│   │   ├── document_controller.py#   Document endpoints
│   │   └── user_controller.py    #   User management
│   ├── services/                 # Business logic layer
│   │   ├── auth_service.py       #   Authentication (AD, email OTP)
│   │   ├── rag_service.py        #   RAG query engine
│   │   ├── ingestion_service.py  #   Document ingestion pipeline
│   │   ├── ingest_worker.py      #   Background ingestion worker
│   │   ├── model_router.py       #   4-tier model router
│   │   ├── document_service.py   #   Document CRUD
│   │   ├── gemini_service.py     #   Google Gemini integration
│   │   ├── deepseek_service.py   #   DeepSeek API integration
│   │   ├── huggingface_service.py#   HuggingFace inference
│   │   ├── opencode_zen_service.py#  OpenCode Zen API
│   │   ├── vision_service.py     #   Image analysis
│   │   ├── web_search_service.py #   DuckDuckGo fallback
│   │   ├── csv_analytics_service.py# CSV analytics
│   │   ├── history_service.py    #   Chat history
│   │   ├── summary_history_service.py# Summary history
│   │   ├── bootstrap_service.py  #   File watcher / bootstrap scan
│   │   ├── model_pull_service.py #   Model downloading (Ollama)
│   │   ├── system_settings_service.py# Dynamic settings
│   │   ├── transcription_service.py# Audio transcription
│   │   ├── training_export_service.py# Training data export
│   │   ├── knowledge_distillation_service.py# Knowledge distillation
│   │   ├── teacher_service.py    #   Teacher model orchestration
│   │   └── multi_model_trainer.py#   Multi-model training
│   ├── db/                       # Database layer
│   │   ├── database.py           #   SQLAlchemy engine & session
│   │   └── models.py             #   ORM models
│   ├── models/                   # Pydantic API schemas
│   │   └── schemas.py
│   ├── security/                 # Authorization
│   │   └── rbac.py               #   Role-based access control
│   ├── utils/                    # Utility modules
│   │   ├── ollama_client.py      #   Ollama API client
│   │   ├── chroma_client.py      #   ChromaDB client
│   │   └── model_cache.py        #   Model cache tracking
│   └── training/                 # ML training pipeline
│       ├── training_config.py    #   Training configuration
│       ├── lora_trainer.py       #   LoRA/QLoRA trainer
│       ├── data_preparer.py      #   Training data preparation
│       ├── checkpoint_manager.py #   Checkpoint management
│       └── training_scheduler.py #   Training scheduler
├── frontend/                     # React + TypeScript web UI
│   ├── src/
│   │   ├── App.tsx               # Main app component
│   │   ├── pages/                # Page components
│   │   ├── api/                  # API client
│   │   ├── theme/                # ZETDC colour palette
│   │   └── components/           # Reusable components
│   ├── index.html
│   ├── vite.config.ts
│   ├── tsconfig.json
│   └── package.json
├── mobile/                       # React Native (Expo) mobile app
│   ├── App.tsx                   # Mobile app entry
│   ├── src/
│   │   ├── screens/              # Screen components
│   │   │   ├── ChatScreen.tsx    #   Chat with EC history
│   │   │   └── DocumentUploadScreen.tsx# Document upload
│   │   └── api/                  # API client
│   ├── app.json
│   ├── tsconfig.json
│   └── package.json
├── localai/                      # Local AI runtime directory
│   └── data/
│       ├── uploads/              # Uploaded files
│       ├── processed/            # Processed files
│       ├── chroma/               # ChromaDB persistent storage
│       ├── ocr/                  # OCR output
│       └── projects/             # Project files
├── models/                       # Local model storage
│   └── llama_local/
├── training/                     # Training data
├── logs/                         # Application logs
├── tests/                        # Test suite
│   └── integration_tests.py
├── scripts/                      # Utility scripts
├── FRS/                          # Functional Requirements Spec
├── FRS2/                         # Extended FRS
├── docs/                         # Project documentation
├── requirements.txt              # Python dependencies
├── run_dev.py                    # Dev launcher (backend + frontend)
├── run.ps1                       # PowerShell run script
├── setup.ps1                     # Setup script
├── reset_doctel.ps1              # Reset script
├── clear_data.ps1                # Data clearing script
└── smoke-tests.ps1               # Smoke test script
```

---

## 4. Architecture & Data Flow

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Users                                 │
│  (Browser / Mobile App / API Clients)                       │
└──────────────┬────────────────────────────┬─────────────────┘
               │                            │
               ▼                            ▼
┌──────────────────────────┐   ┌──────────────────────────┐
│   Frontend (Vite+React)  │   │   Mobile (Expo + RN)     │
│   localhost:5173         │   │   Physical Device        │
└──────────────┬───────────┘   └──────────────┬───────────┘
               │                              │
               └──────────┬───────────────────┘
                          │ HTTP REST
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                 FastAPI Backend (port 8000)                   │
│                                                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │ Auth     │  │ Document │  │ Chat/    │  │ System   │    │
│  │ Service  │  │ Service  │  │ RAG      │  │ Settings │    │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘    │
│       │             │             │              │          │
│       └─────────────┼─────────────┼──────────────┘          │
│                     │             │                         │
│              ┌──────▼─────────────▼──────┐                  │
│              │     Model Router (4-Tier)  │                  │
│              └──────┬─────────────┬──────┘                  │
│                     │             │                         │
└─────────────────────┼─────────────┼─────────────────────────┘
                      │             │
     ┌────────────────▼──┐   ┌──────▼────────────┐
     │   Ollama Server    │   │   ChromaDB        │
     │   (Local LLMs)     │   │   (Vector Store)  │
     │   port 11434       │   │   (Persistent)    │
     └────────────────┬───┘   └───────────────────┘
                      │
         ┌────────────┼────────────┐
         ▼            ▼            ▼
    ┌────────┐  ┌──────────┐  ┌──────────┐
    │Qwen3:4b│  │Qwen3:8b  │  │Llama 3.2 │
    │(4B)    │  │(8B)      │  │(3B)      │
    └────────┘  └──────────┘  └──────────┘

  External APIs (optional):
    ┌──────────┐  ┌──────────┐  ┌──────────────┐
    │ Gemini   │  │ DeepSeek │  │ HuggingFace  │
    │ (Google) │  │(OpenCode)│  │              │
    └──────────┘  └──────────┘  └──────────────┘
```

### Document Ingestion Flow

```
User uploads file
       │
       ▼
┌──────────────────┐
│  File received   │
│  - SHA256 hash   │
│  - MIME detect   │
│  - Save to disk  │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│  Extract text    │
│  - PDF (PyPDF2)  │
│  - DOCX (python-docx)│
│  - Images (OCR)  │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│  Chunk text      │
│  (configurable   │
│   size/overlap)  │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│  Generate        │
│  embeddings via  │
│  Ollama (nomic)  │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│  Store in        │
│  ChromaDB        │
│  (per-project)   │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│  Run AI analysis │
│  - Summarize     │
│  - Extract       │
│    entities,     │
│    topics,        │
│    sentiment,    │
│    actions,      │
│    decisions     │
└──────────────────┘
```

### RAG Query Flow

```
User asks a question
       │
       ▼
┌──────────────────┐
│  1. Embed query  │
│  (Ollama embed)  │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│  2. ChromaDB     │
│     similarity   │
│     search       │
│     (top_k)      │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│  3. Build        │
│     context from │
│     retrieved    │
│     chunks       │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│  4. Model Router │
│     selects best │
│     available    │
│     LLM          │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│  5. Generate     │
│     answer with  │
│     citations    │
│     & sources    │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│  6. Return       │
│     answer +     │
│     citations +  │
│     cross-refs   │
└──────────────────┘
```

---

## 5. Backend Components

### 5.1 Core Application (`app/main.py`)

The FastAPI application entry point that:

- Configures CORS middleware
- Adds debug logging middleware for requests/responses
- Registers exception handlers (422 validation, HTTP exceptions, unhandled errors)
- Initializes the database on startup
- Loads system settings dynamically
- Configures rotating file logging
- Defines all API routes (documented below)

### 5.2 Configuration (`app/config.py` + `app/config.yaml`)

A Pydantic-based configuration system with a layered override strategy:

1. **Default values** in Pydantic model definitions
2. **`.env` file** (auto-loaded from project root)
3. **Environment variables** (prefixed with `DOCINTEL_`)
4. **`config.yaml`** YAML file (highest priority)

Key configuration groups:

| Group | Description |
|-------|-------------|
| Core | `base_dir`, `environment`, `offline_only`, `bind_host`, `port` |
| LLM | Ollama model names, Gemini API key, DeepSeek API key |
| Model Routing | RAM thresholds, automatic switching, available models |
| Auth | AD/LDAP settings, email OTP, token expiry |
| RAG | `chunk_size`, `chunk_overlap`, `top_k`, `use_mmr` |
| Storage | Upload, processed, vector DB paths |
| UI | Poll intervals, model selector, animations |
| Security | HTTPS, SQLite encryption, Windows EFS |
| RBAC | Roles (admin, analyst, viewer) |
| Training | LoRA parameters, base model, QLoRA settings |
| Bootstrap | Scan paths, scheduling, OCR |
| ZETDC | System prompt, tags, web search toggle |

### 5.3 Controllers (`app/controllers/`)

| Controller | Endpoints | Description |
|-----------|-----------|-------------|
| `auth_controller.py` | `/auth/login`, `/auth/email/*`, `/auth/me` | Authentication routes |
| `document_controller.py` | Document CRUD, upload, analysis | Document management |
| `user_controller.py` | User management | User administration |

### 5.4 Services (`app/services/`)

| Service | Responsibility |
|---------|---------------|
| `auth_service.py` | AD/LDAP authentication, email OTP, session management, token generation |
| `rag_service.py` | RAG pipeline — embed query, retrieve from ChromaDB, build context, generate answer with citations |
| `ingestion_service.py` | Document text extraction (PDF, DOCX, OCR), chunking, embedding, analysis, auto-training trigger |
| `ingest_worker.py` | Background async worker for ingestion queue |
| `model_router.py` | 4-tier intelligent model selection (LoRA → Ollama → Cloud → Web) |
| `document_service.py` | Document CRUD operations |
| `gemini_service.py` | Google Gemini API integration |
| `deepseek_service.py` | DeepSeek API integration (via OpenCode Go proxy) |
| `huggingface_service.py` | HuggingFace inference API |
| `opencode_zen_service.py` | OpenCode Zen API integration |
| `vision_service.py` | Image analysis using vision models (llava) |
| `web_search_service.py` | DuckDuckGo search fallback (last resort) |
| `bootstrap_service.py` | Directory scanning and file watcher for auto-ingestion |
| `model_pull_service.py` | Ollama model download management |
| `system_settings_service.py` | Dynamic system settings with live apply |
| `history_service.py` | Chat session & message history |
| `summary_history_service.py` | Document summary history tracking |
| `csv_analytics_service.py` | CSV data analysis |
| `transcription_service.py` | Audio file transcription |
| `training_export_service.py` | Export training data |
| `multi_model_trainer.py` | Orchestrates training across multiple models |
| `knowledge_distillation_service.py` | Distills knowledge from teacher to student models |
| `teacher_service.py` | Manages teacher model interactions |

---

## 6. Database Schema

### Entity-Relationship Diagram

```
users
├── id (PK)
├── username (UNIQUE)
├── ec_number
├── email
├── display_name
├── role (admin|analyst|viewer)
└── created_at
    ├── owned_projects → projects
    ├── memberships → project_members
    └── identity_providers → user_identity_providers

user_identity_providers
├── id (PK)
├── user_id (FK → users)
├── provider (ec_password|email_otp)
├── identity
├── verified
└── last_login_at

auth_sessions
├── token (PK)
├── user_id (FK → users)
├── provider
├── identity
├── display_name
└── created_at

projects
├── id (PK)
├── name
├── owner_user_id (FK → users)
└── created_at
    ├── owner → users
    ├── members → project_members
    ├── documents → documents
    └── sessions → sessions

project_members
├── id (PK)
├── project_id (FK → projects)
├── user_id (FK → users)
├── role_in_project
└── UNIQUE(project_id, user_id)

documents
├── id (PK)
├── project_id (FK → projects)
├── uploaded_by_user_id (FK → users)
├── filename
├── path
├── mime_type
├── sha256
├── pages
├── doc_type
├── doc_date
├── is_public
├── auto_project_confidence
├── needs_project_review
├── tags_json
├── analysis_ready
├── ingestion_started
├── ingestion_completed
├── ingestion_failed
├── status (uploaded|...)
├── ingest_step
├── ingest_percent
├── ingest_message
├── error_message
├── detected_type
├── created_at
└── updated_at
    ├── project → projects
    ├── analysis → doc_analysis
    ├── prompts → suggested_prompts
    └── chunks → chunks

doc_analysis
├── id (PK)
├── document_id (FK → documents)
├── executive_summary
├── detailed_summary
├── sentiment
├── entities_json
├── topics_json
├── action_items_json
└── decisions_json

suggested_prompts
├── id (PK)
├── document_id (FK → documents)
├── prompt_text
└── created_at

chunks
├── id (PK)
├── document_id (FK → documents)
├── project_id (FK → projects)
├── chunk_index
├── text
├── citation_ref
├── embedding_id (FK → embeddings)
└── created_at

embeddings
├── id (PK)
├── vector_ref (ChromaDB ID)
└── created_at

sessions (Chat)
├── id (PK)
├── session_uuid (UNIQUE)
├── project_id (FK → projects)
├── document_id (FK → documents)
├── user_id (FK → users)
├── model_name
├── title
├── scope (global|project|document)
├── archived
├── started_at
└── updated_at
    └── messages → messages

messages
├── id (PK)
├── session_id (FK → sessions)
├── role (user|assistant|system)
├── content
├── status (pending|done|failed)
├── citations_json
└── created_at

document_links
├── id (PK)
├── from_document_id (FK → documents)
├── to_document_id (FK → documents)
├── relation
├── confidence
└── created_at

diagrams
├── id (PK)
├── project_id (FK → projects)
├── session_id (FK → sessions)
├── title
├── mermaid
├── drawing_prompt
├── version
└── created_at

system_settings
├── key (PK)
├── value_json
└── updated_at

settings_audit
├── id (PK)
├── setting_key
├── old_value
├── new_value
├── changed_by_user_id
└── changed_at
```

---

## 7. AI / ML Pipeline

### 7.1 Document Analysis

When a document is uploaded, the ingestion pipeline performs:

1. **Text Extraction** — PDF text, DOCX text, or OCR (Tesseract) for images
2. **Chunking** — Splits text into configurable chunks (default 1000 chars, 150 overlap)
3. **Embedding** — Generates vector embeddings via Ollama (`nomic-embed-text`)
4. **Vector Storage** — Stores chunks + embeddings in ChromaDB (per-project collections)
5. **AI Analysis** — Uses the selected LLM to extract:
   - Executive summary
   - Detailed summary (multi-paragraph)
   - Named entities
   - Key entities (categorized)
   - Topics
   - Sentiment
   - Action items
   - Decisions
   - Suggested prompts for follow-up queries

### 7.2 RAG (Retrieval-Augmented Generation)

The RAG pipeline (`rag_service.py`):

1. Embeds the user query using `nomic-embed-text`
2. Queries ChromaDB for similar chunks (configurable `top_k`, default 6)
3. Supports MMR (Maximum Marginal Relevance) for diversity
4. Can scope search to a specific project or document
5. Deduplicates results and builds context
6. Generates answer with the selected LLM
7. Returns answer with citations (filename, chunk index, snippet) and cross-references

### 7.3 LoRA / QLoRA Training (`app/training/`)

The training pipeline enables fine-tuning local models on organizational documents:

- **Base models**: Supports HuggingFace models (default: `meta-llama/Llama-3.2-3B-Instruct`)
- **Quantization**: 4-bit QLoRA support (bitsandbytes)
- **Adapters**: LoRA with configurable rank (`r: 8`)
- **Data preparation**: Converts documents + Q&A into training format
- **Checkpoint management**: Saves and manages training checkpoints
- **Scheduling**: Optional periodic training

### 7.4 Knowledge Distillation

The `knowledge_distillation_service.py` enables:

- Using a larger "teacher" model (e.g., DeepSeek, Gemini) to generate high-quality training data
- Training a smaller "student" model (local LoRA adapter) on the distilled data
- Improving local model quality without relying on cloud APIs at inference time

---

## 8. Model Routing (4-Tier)

The `model_router.py` implements an intelligent 4-tier fallback system:

| Tier | Model Source | Latency | Privacy | Use Case |
|------|------------|---------|---------|----------|
| **1** | Local LoRA Adapter | Fastest | ✅ Full | Trained on org data |
| **2** | Ollama (local LLM) | Fast | ✅ Full | General Q&A, RAG |
| **3** | Cloud Teacher (DeepSeek/Gemini) | Medium | ❌ | Complex analysis |
| **4** | Web Search (DuckDuckGo) | Slow | ❌ | Current events |

### Automatic Model Selection

Based on available system RAM, the router automatically selects the best local model:

| Available RAM | Model Selected |
|-------------|---------------|
| ≥ 7000 MB | Qwen3:8b (if enabled) |
| ≥ 6000 MB | Primary text model (e.g., qwen3:4b) |
| < 6000 MB | Fallback model (e.g., qwen3:4b) |

### Supported Models

| Model | ID | Size | Purpose |
|-------|-----|------|---------|
| Qwen3 4B | `qwen3:4b` | ~2.5 GB | Default text generation |
| Qwen3 8B | `qwen3:8b` | ~4.5 GB | High-quality generation |
| Llama 3.2 | `llama3.2:latest` | ~2-8 GB | Alternative text |
| LLaVA | `llava:7b` | ~4 GB | Vision/multimodal |
| Nomic Embed Text | `nomic-embed-text` | ~0.5 GB | Text embeddings |
| Gemma 2 | `gemma2:2b` | ~1.5 GB | Lightweight tasks |

---

## 9. Authentication & Authorization

### 9.1 Authentication Methods

**Method 1: EC Number + Password (Active Directory)**
- Uses LDAP3 to authenticate against ZETDC's Active Directory
- Configurable via `ad_url`, `ad_domain`, `ad_base_dn`, `ad_use_tls`

**Method 2: Email OTP (One-Time Password)**
- Sends a verification code to the user's `@zetdc.co.zw` email
- Supports SMTP or configurable email server API
- Domain-restricted via `allowed_email_domain`

### 9.2 Session Management

- **Access Token**: JWT-like, expires in 30 minutes (configurable)
- **Refresh Token**: Longer-lived (7 days), enables auto-sign-in
- **Auto Sign-in Modal**: Configurable UI behavior

### 9.3 Role-Based Access Control (RBAC)

| Role | Privileges |
|------|-----------|
| **admin** | Full system access, all projects, user management |
| **analyst** | Document analysis, chat, project membership |
| **viewer** | Read-only access to assigned documents/projects |

Features:
- Auto-assign uploader as project member
- Per-project role assignment via `ProjectMember`
- Document-level access control (owner, project, or public)
- Project membership enforcement for queries

---

## 10. Frontend (Web)

The web frontend is a React + TypeScript application built with Vite.

### Key Pages

| Page | Description |
|------|-------------|
| `DocumentViewPage.tsx` | Document analysis viewer with AI copilot |
| Chat interface | Session-based Q&A with document context |

### API Client

- Located in `src/api/client.ts`
- Communicates with FastAPI backend
- Configurable `VITE_API_BASE_URL` (default: `http://localhost:8000`)

### Theme

- ZETDC-branded colour palette defined in `src/theme/colors.ts`
- Consistent with organizational branding guidelines

### UI Features

- Model selector (enable/disable via config)
- Scope switching (global / project / document)
- Pull modal for downloading models
- Intro animation (configurable duration)
- Greeting messages (customizable list)
- Chat while ingesting support

---

## 11. Mobile App

The mobile app is built with React Native (Expo SDK 54).

### Key Screens

| Screen | Description |
|--------|-------------|
| `ChatScreen.tsx` | Chat interface with EC number history |
| `DocumentUploadScreen.tsx` | Document upload with metadata |

### Features

- Document upload via `expo-document-picker`
- File system access via `expo-file-system`
- Audio/video playback via `expo-av`
- Date/time picker for metadata
- Async storage for local caching
- Configurable API base URL via `EXPO_PUBLIC_API_BASE_URL`

### Build

- Android: `eas build -p android --local`
- iOS: Expo start with iOS simulator

---

## 12. Configuration Reference

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DOCINTEL_BASE_DIR` | `C:\LocalAI` | Base storage directory |
| `DOCINTEL_ENV` | `development` | Environment name |
| `DOCINTEL_OFFLINE_ONLY` | `true` | Disable external API calls |
| `DOCINTEL_BIND_HOST` | `127.0.0.1` | Server bind address |
| `DOCINTEL_PORT` | `8000` | Server port |
| `DOCINTEL_TEXT_MODEL` | `qwen3:4b` | Primary text LLM |
| `DOCINTEL_FALLBACK_TEXT_MODEL` | `qwen3:4b` | Fallback text LLM |
| `DOCINTEL_VISION_MODEL` | `llava:7b` | Vision model |
| `DOCINTEL_EMBED_MODEL` | `nomic-embed-text` | Embedding model |
| `DOCINTEL_OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `GEMINI_API_KEY` | — | Google Gemini API key |
| `DEEPSEEK_API_KEY` | — | DeepSeek API key |
| `DOCINTEL_AD_URL` | — | LDAP/AD server URL |
| `DOCINTEL_AD_DOMAIN` | — | AD domain |
| `DOCINTEL_AD_BASE_DN` | — | AD base DN |
| `DOCINTEL_MAX_CONTEXT_TOKENS` | `3000` | Max context tokens |
| `DOCINTEL_CHUNK_SIZE` | `1000` | Chunk size (characters) |
| `DOCINTEL_CHUNK_OVERLAP` | `150` | Chunk overlap (characters) |
| `DOCINTEL_TOP_K` | `6` | Top-K retrieval |
| `DOCINTEL_USE_MMR` | `true` | Enable MMR diversity |
| `DOCINTEL_CORS_ORIGINS` | `*` | Allowed CORS origins |
| `DOCINTEL_ALLOWED_EMAIL_DOMAIN` | `zetdc.co.zw` | Email domain restriction |
| `DOCINTEL_ENABLE_QWEN_9B` | `false` | Enable larger model |
| `DOCINTEL_AUTOMATIC_SWITCHING` | `true` | Auto model switching |
| `DOCINTEL_DEFAULT_MODEL` | — | Override default model |
| `DOCINTEL_MIN_FREE_RAM_FOR_8B_MB` | `6000` | RAM threshold for 8B |
| `DOCINTEL_MIN_FREE_RAM_FOR_QWEN9B_MB` | `7000` | RAM threshold for 9B |

### YAML Configuration

All environment variables can also be set in `app/config.yaml` under their respective sections:

```yaml
text_model: "qwen3:4b"
offline_only: true
auth:
  access_token_minutes: 30
  refresh_token_days: 7
rag:
  chunk_size: 1000
  top_k: 6
ui:
  show_intro_animation: true
storage:
  organize_by_project: true
```

---

## 13. API Endpoints

The FastAPI backend exposes the following API routes:

### Authentication

| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/login` | Login with EC number + password |
| POST | `/auth/email/request` | Request email OTP |
| POST | `/auth/email/verify` | Verify email OTP |
| GET | `/auth/me` | Get current user info |

### Documents

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/documents/upload` | Upload a document |
| GET | `/api/documents` | List documents |
| GET | `/api/documents/{id}` | Get document details |
| DELETE | `/api/documents/{id}` | Delete document |
| GET | `/api/documents/{id}/analysis` | Get document analysis |
| GET | `/api/documents/{id}/prompts` | Get suggested prompts |

### Chat / RAG

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/ask` | Ask a question (RAG) |
| POST | `/api/chat` | Chat with context |
| GET | `/api/sessions` | List chat sessions |
| GET | `/api/sessions/{uuid}` | Get session messages |

### Projects

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/projects` | Create project |
| GET | `/api/projects` | List projects |
| GET | `/api/projects/{id}` | Get project details |
| DELETE | `/api/projects/{id}` | Delete project |

### System

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/api/models` | List available models |
| POST | `/api/models/pull` | Pull a model |
| GET | `/api/settings` | Get system settings |
| PUT | `/api/settings` | Update system settings |

### Training

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/training/now` | Trigger training cycle |
| GET | `/api/training/status` | Training status |
| POST | `/api/training/distill` | Trigger knowledge distillation |

> **Note:** Full Swagger documentation is available at `/docs` when the server is running.

---

## 14. Deployment & Running

### Prerequisites

- Python 3.12+
- Node.js + npm
- Ollama installed and running (for local LLMs)
- Tesseract OCR (optional, for image text extraction)

### Quick Start

```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Install frontend dependencies
cd frontend && npm install

# 3. Install mobile dependencies
cd ../mobile && npm install

# 4. Set environment variables (optional)
$env:DOCINTEL_ENV = "development"
$env:DOCINTEL_CORS_ORIGINS = "http://localhost:5173"

# 5. Run both backend and frontend
python run_dev.py

# Or run separately:
# Backend only:
uvicorn app.main:app --reload --port 8000
# Frontend only:
cd frontend && npm run dev
```

### Helper Scripts

| Script | Purpose |
|--------|---------|
| `run_dev.py` | Launches backend + frontend concurrently |
| `run.ps1` | PowerShell run script |
| `setup.ps1` | First-time setup (dependencies, directories) |
| `reset_doctel.ps1` | Reset application state |
| `clear_data.ps1` | Clear uploaded/processed data |
| `smoke-tests.ps1` | Run smoke tests |

### Production Considerations

- Set `DOCINTEL_ENV=production`
- Configure proper `DOCINTEL_BASE_DIR` for persistent storage
- Enable `security.use_local_https` if needed
- Configure Active Directory for organizational auth
- Set up proper email server for OTP delivery
- Consider using a more robust database (PostgreSQL) for production scale
- Configure proper backup strategy for ChromaDB and SQLite

---

## Appendix: Project Naming

Throughout the codebase, the system is referred to by multiple names:

| Name | Context |
|------|---------|
| **DocTel** | User-facing brand name, system identity in ZETDC |
| **DocIntel** | Internal codename, used in code (`app.title = "DocIntel"`) |
| **DocIntel Frontend** | Web frontend package name |
| **DocIntel Mobile** | Mobile app package name |

The system is configured via the ZETDC system prompt (in `config.yaml`) to identify itself as **DocTel** to end users.

---

*This document provides a comprehensive overview of the DocTel system architecture. For implementation details, refer to the individual source files and inline documentation.*
