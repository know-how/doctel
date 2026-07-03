# DocTel Technical Deep-Dive Document

**Version:** 1.0  
**Date:** May 10, 2026  
**Audience:** Developers, DevOps, Technical Architects, IT Managers

---

## Table of Contents

1. [System Architecture](#system-architecture)
2. [Component Interactions](#component-interactions)
3. [Data Pipeline Details](#data-pipeline-details)
4. [API Specifications](#api-specifications)
5. [Database Schema](#database-schema)
6. [LLM Integration Layer](#llm-integration-layer)
7. [Vector Database Operations](#vector-database-operations)
8. [Deployment Architecture](#deployment-architecture)
9. [Performance Optimization](#performance-optimization)
10. [Scalability Considerations](#scalability-considerations)

---

## 1. System Architecture

### 1.1 Microservices Breakdown

```
┌─────────────────────────────────────────────────────────┐
│              FastAPI Backend (main.py)                  │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Controllers Layer (route handlers)                    │
│  ├─ auth_controller.py      (Login, Token manage)      │
│  ├─ document_controller.py   (CRUD operations)         │
│  └─ user_controller.py       (User management)         │
│                                                         │
│  Services Layer (business logic)                       │
│  ├─ ingestion_service.py     (Document processing)     │
│  ├─ rag_service.py           (Q&A + retrieval)        │
│  ├─ auth_service.py          (Authentication)         │
│  ├─ model_router.py          (LLM selection)          │
│  ├─ bootstrap_service.py     (System startup)         │
│  ├─ gemini_service.py        (Gemini API client)      │
│  └─ ...more services...      (Domain-specific)        │
│                                                         │
│  Data Access Layer (ORM, Database)                     │
│  ├─ database.py              (SQLAlchemy engine)       │
│  └─ models.py                (ORM model definitions)   │
│                                                         │
│  Security Layer (RBAC, Auth)                           │
│  └─ rbac.py                  (Access control)          │
│                                                         │
└─────────────────────────────────────────────────────────┘

External Services:
├─ PostgreSQL Database      (SQLAlchemy ORM)
├─ Chroma Vector Store      (Vector search)
├─ Ollama LLM Runtime       (Local models)
├─ Gemini API               (Cloud models)
└─ SMTP Mail Server         (Email OTP)
```

### 1.2 Technology Decisions & Rationale

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Framework | FastAPI | Async, type hints, auto-docs, high performance |
| Language | Python 3.10+ | Rich ML/NLP libraries, rapid development |
| Database | PostgreSQL | ACID compliance, complex queries, proven at scale |
| ORM | SQLAlchemy 2.0 | Async support, type safety, query optimization |
| Vector DB | Chroma | Easy setup, semantic search, lightweight |
| LLM Local | Ollama | Privacy-first, local control, multiple models |
| LLM Cloud | Gemini API | Fallback, advanced capabilities, reasonable cost |
| Auth | Email OTP | No infrastructure required, secure, user-friendly |
| Frontend | React + Vite | Fast bundling, modern DX, mobile-ready |
| Mobile | React Native | Code sharing, fast development, iOS + Android |

---

## 2. Component Interactions

### 2.1 Request-Response Flow

```
USER REQUEST
    ↓
[FastAPI Middleware]
├─ CORS handling
├─ Request logging
└─ Exception handling
    ↓
[Authentication Middleware]
├─ Verify token
├─ Get user
└─ Inject into request
    ↓
[Route Handler (Controller)]
├─ Validate input
├─ Call service(s)
├─ Format response
└─ Return JSON
    ↓
[Services Layer]
├─ Database operations (via ORM)
├─ Vector DB operations
├─ External API calls
└─ Business logic
    ↓
[Data Access Layer]
├─ Query construction
├─ Execute via SQLAlchemy
└─ Return results
    ↓
RESPONSE TO USER
```

### 2.2 Async/Await Pattern

DocTel uses async/await throughout for non-blocking I/O:

```python
# Example: Upload and ingest document asynchronously
@app.post("/api/documents/upload")
async def upload_document(
    file: UploadFile,
    project_id: int,
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user)
):
    # Fast: Store metadata
    doc = Document(...)
    db.add(doc)
    await db.commit()
    
    # Async: Enqueue processing (returns immediately)
    await enqueue_ingest(doc_id=doc.id)
    
    # Return to user while processing continues
    return {"status": "accepted", "document_id": doc.id}

# Background: Ingest worker processes asynchronously
async def ingest_worker():
    while True:
        doc = await get_next_queued_document()
        await ingest_document(doc)  # 30-60 seconds
        doc.status = "completed"
        await db.commit()
```

### 2.3 Error Handling Strategy

```
Try:
  ├─ Execute operation
  └─ Return result

Except HTTPException:
  └─ Re-raise with proper status code

Except SQLAlchemy.Exception:
  ├─ Log error
  ├─ Retry if transient
  └─ Return 500 or appropriate status

Except External Service Error:
  ├─ Try fallback
  ├─ Log incident
  └─ Return degraded response

Finally:
  ├─ Cleanup resources
  └─ Close connections
```

---

## 3. Data Pipeline Details

### 3.1 Document Ingestion Pipeline

```
INPUT: UploadFile (PDF/DOCX/TXT)

STAGE 1: VALIDATION
├─ Check file extension
├─ Validate MIME type
├─ Check file size (<100MB)
├─ Generate SHA256 hash
├─ Check for duplicates
└─ Reject if failed

STAGE 2: TEXT EXTRACTION
├─ PDF: PyPDF2.PdfReader
├─ DOCX: python-docx
├─ TXT: Direct read with UTF-8 encoding
└─ Store raw text in database

STAGE 3: CHUNKING
├─ Split text into chunks (~1000 tokens each)
├─ Add 200-token overlap between chunks
├─ Number chunks sequentially
├─ Store chunk + index in database
└─ Prepare for embedding

STAGE 4: EMBEDDING GENERATION
├─ For each chunk:
│  ├─ Convert chunk text to embedding vector
│  ├─ Model: nomic-embed-text (384-dim)
│  ├─ Store embedding in database
│  └─ Store vector reference in Chroma
└─ Index in Chroma by project_id

STAGE 5: ANALYSIS
├─ Executive Summary
│  └─ Select top chunks → LLM → 10-sentence summary
├─ Detailed Summary
│  └─ Full chunked text → LLM → Bullet-point summary
├─ Entity Extraction
│  └─ Text → NER prompt → Parse entities → Store JSON
├─ Sentiment Analysis
│  └─ Summary → Classification → Pos/Neu/Neg/Urgent
├─ Topic Extraction
│  └─ Full text → LLM → Topics + relevance scores
├─ Action Items
│  └─ Text → LLM → Extract tasks + owners + dates
└─ Store all in doc_analysis table

STAGE 6: PROMPT GENERATION
├─ Analyze document type + topics
├─ Generate 3-5 context-specific questions
├─ Store in suggested_prompts table
└─ Ready for display

OUTPUT: Document marked analysis_ready=true
```

### 3.2 Chunk Structure Example

```python
# Document: HSE_Policy_2026.pdf (25 pages, ~7500 tokens)

Chunk 0:
  ├─ Tokens: 0-1000
  ├─ Text: "Safety Policy Overview. This document outlines..."
  ├─ Embedding: [0.23, 0.15, ..., 0.41]  # 384 dimensions
  └─ Metadata: {"filename": "HSE_Policy_2026.pdf", "chunk_index": 0}

Chunk 1:
  ├─ Tokens: 800-1800  # 200-token overlap
  ├─ Text: "... policies outlined above. Section 2 covers..."
  ├─ Embedding: [0.12, 0.33, ..., 0.28]
  └─ Metadata: {"filename": "HSE_Policy_2026.pdf", "chunk_index": 1}

... (more chunks)

Chunk 7:
  ├─ Tokens: 6500-7500
  ├─ Text: "Document version 2.1. Approved by [names]..."
  ├─ Embedding: [0.45, 0.22, ..., 0.19]
  └─ Metadata: {"filename": "HSE_Policy_2026.pdf", "chunk_index": 7}
```

### 3.3 Embedding Model Specs

```
Model: nomic-embed-text (via Ollama)

Specifications:
├─ Input: Text (any length, auto-tokenized)
├─ Output: 384-dimensional vector
├─ Normalized: L2 normalized for cosine similarity
├─ Latency: ~50ms per chunk (batch processing faster)
├─ Batch Size: 32 chunks optimal for memory/speed
└─ Precision: Float32

Encoding Example:
Input:  "What are the safety requirements?"
Output: [-0.023, 0.145, ..., 0.287]  # 384 values

Distance Metric: Cosine similarity (Chroma uses this)
Range: 0 (identical) to 2 (opposite)
```

---

## 4. API Specifications

### 4.1 Authentication Endpoints

#### POST /api/auth/request-otp
**Purpose:** Initiate email OTP flow  
**Request:**
```json
{
  "email": "user@zetdc.co.zw"
}
```
**Response (200):**
```json
{
  "status": "success",
  "message": "OTP sent to email",
  "request_id": "req_abc123"
}
```
**Process:**
1. Generate 6-digit OTP
2. Store with 15-min expiry
3. Send via SMTP
4. Return request_id

---

#### POST /api/auth/verify-otp
**Purpose:** Verify OTP and get auth token  
**Request:**
```json
{
  "email": "user@zetdc.co.zw",
  "otp": "123456"
}
```
**Response (200):**
```json
{
  "token": "eyJhbGciOiJIUzI1NiIs...",
  "user": {
    "id": 1,
    "username": "john.doe",
    "email": "user@zetdc.co.zw",
    "role": "analyst"
  }
}
```
**Process:**
1. Verify OTP matches + not expired
2. Create or get user
3. Generate JWT token (24-hour expiry)
4. Return token + user data

---

### 4.2 Document Upload Endpoint

#### POST /api/documents/upload
**Purpose:** Upload document for analysis  
**Headers:**
```
Authorization: Bearer {token}
Content-Type: multipart/form-data
```
**Request:**
```
file: <binary PDF/DOCX/TXT>
project_id: 1
doc_type: "Policy"
doc_date: "2026-05-10"
tags: ["Safety", "2026"]
```
**Response (202 Accepted):**
```json
{
  "document_id": "doc_123",
  "status": "uploaded",
  "message": "Document queued for analysis",
  "estimated_processing_time": "30-60 seconds"
}
```
**Process:**
1. Validate file (format, size, hash)
2. Store in database + file system
3. Enqueue for ingestion worker
4. Return immediately (202 Accepted)
5. Client polls status endpoint for progress

---

### 4.3 Question Answering Endpoint

#### POST /api/documents/{doc_id}/ask
**Purpose:** Ask question about document  
**Headers:**
```
Authorization: Bearer {token}
Content-Type: application/json
```
**Request:**
```json
{
  "question": "What are the key safety requirements?",
  "session_id": "sess_abc123"  // optional, creates if not provided
}
```
**Response (200):**
```json
{
  "answer_text": "According to the policy, there are three key requirements: [Doc: HSE_Policy_2026.pdf, chunk 5] 1) Pre-shift inspection...",
  "citations": [
    {
      "filename": "HSE_Policy_2026.pdf",
      "chunk_index": 5,
      "text_preview": "Pre-shift equipment inspection must be completed by..."
    },
    {
      "filename": "HSE_Policy_2026.pdf",
      "chunk_index": 7,
      "text_preview": "Incident reporting procedures..."
    }
  ],
  "mermaid_code": "",  // empty unless force_diagram=true
  "used_model": "llama2"
}
```
**Process:**
1. Verify user has access to document
2. Embed question (384-dim vector)
3. Query Chroma for top-6 chunks
4. Build context from chunks
5. Send to LLM (Ollama or Gemini)
6. Parse response for citations
7. Return answer + citations

---

### 4.4 Cross-Document Query

#### POST /api/projects/{proj_id}/ask
**Purpose:** Ask question across all documents in project  
**Request:**
```json
{
  "question": "Compare budget allocations across all reports",
  "scope": "project"
}
```
**Response (200):**
```json
{
  "answer_text": "Based on Q1, Q2, and Q3 reports: [Doc: Q1_Report.pdf, chunk 3] Q1 budget was $X, [Doc: Q2_Report.pdf, chunk 2] Q2 was $Y...",
  "citations": [
    {"filename": "Q1_Report.pdf", "chunk_index": 3, ...},
    {"filename": "Q2_Report.pdf", "chunk_index": 2, ...},
    {"filename": "Q3_Report.pdf", "chunk_index": 4, ...}
  ],
  "documents_searched": 3,
  "used_model": "llama2"
}
```

---

## 5. Database Schema

### 5.1 ERD Relationships

```
users (1) ←→ (many) projects
  └─ projects (1) ←→ (many) documents
  └─ documents (1) ←→ (1) doc_analysis
  └─ documents (1) ←→ (many) chunks
  └─ chunks (1) ←→ (1) embeddings
  └─ documents (1) ←→ (many) suggested_prompts

documents (1) ←→ (many) sessions
  └─ sessions (1) ←→ (many) messages

projects (1) ←→ (many) project_members
  └─ project_members ←→ users
```

### 5.2 Key Table Definitions

#### users
```sql
CREATE TABLE users (
  id SERIAL PRIMARY KEY,
  username VARCHAR(100) UNIQUE NOT NULL,
  email VARCHAR(100) INDEX,
  ec_number VARCHAR(50) INDEX,
  display_name VARCHAR(200),
  role VARCHAR(20),  -- 'admin', 'analyst', 'viewer'
  created_at TIMESTAMP DEFAULT NOW()
);
```

#### documents
```sql
CREATE TABLE documents (
  id SERIAL PRIMARY KEY,
  project_id INTEGER FK,
  uploaded_by_user_id INTEGER FK,
  filename VARCHAR(300) NOT NULL,
  mime_type VARCHAR(50),
  sha256 VARCHAR(64) UNIQUE INDEX,  -- Prevent duplicates
  pages INTEGER,
  doc_type VARCHAR(50),  -- 'Policy', 'Report', etc.
  status VARCHAR(50) INDEX,  -- 'uploaded|ingesting|completed|failed'
  ingest_step VARCHAR(100),  -- 'extracting|chunking|embedding|summarizing'
  ingest_percent INTEGER,  -- 0-100
  analysis_ready BOOLEAN DEFAULT FALSE,
  ingestion_started BOOLEAN,
  ingestion_completed BOOLEAN,
  ingestion_failed BOOLEAN,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP
);
```

#### chunks
```sql
CREATE TABLE chunks (
  id SERIAL PRIMARY KEY,
  document_id INTEGER FK,
  project_id INTEGER FK,
  chunk_index INTEGER,  -- 0, 1, 2, ...
  text TEXT NOT NULL,  -- 1000 tokens
  citation_ref VARCHAR(100),  -- "HSE_Policy.pdf:chunk_5"
  embedding_id INTEGER FK,
  created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for fast retrieval
CREATE INDEX idx_chunks_document_id ON chunks(document_id);
CREATE INDEX idx_chunks_project_id ON chunks(project_id);
```

#### doc_analysis
```sql
CREATE TABLE doc_analysis (
  id SERIAL PRIMARY KEY,
  document_id INTEGER FK UNIQUE,
  executive_summary TEXT,  -- 5-10 sentences
  detailed_summary TEXT,   -- Bullet points
  sentiment VARCHAR(20),   -- Positive|Neutral|Negative|Urgent
  entities_json TEXT,      -- JSON array
  topics_json TEXT,        -- JSON with relevance scores
  action_items_json TEXT,  -- JSON with tasks/owners/dates
  decisions_json TEXT      -- JSON with decisions
);
```

#### embeddings (Chroma-managed)
```sql
-- Metadata stored in Chroma
-- Python object references:
{
  "project_id": "1",
  "document_id": "123",
  "chunk_index": "5",
  "filename": "HSE_Policy_2026.pdf"
}

-- Chroma stores vectors separately, optimized for search
```

---

## 6. LLM Integration Layer

### 6.1 Model Router Logic

```python
async def select_text_model(task: str = "rag") -> str:
    """Select best model for task with fallback"""
    
    # Priority 1: User-forced model
    if settings.force_model:
        return settings.force_model
    
    # Priority 2: Task-specific preferred models
    task_preferences = {
        "rag": ["llama2", "mistral", "neural-chat"],
        "summarization": ["llama2", "mistral"],
        "entity_extraction": ["llama2", "neural-chat"],
        "sentiment": ["mistral", "neural-chat", "llama2"]
    }
    
    preferred = task_preferences.get(task, ["llama2"])
    
    # Priority 3: Check which models are active
    active_models = load_model_cache()
    
    for model in preferred:
        if model in active_models and active_models[model]["status"] == "loaded":
            return model
    
    # Priority 4: Try fallback models
    for model in preferred:
        if can_pull_model(model):
            await pull_model(model)
            return model
    
    # Priority 5: Last resort - any available model
    available = [m for m in active_models if active_models[m]["status"] != "failed"]
    if available:
        return available[0]
    
    # No model available
    raise ValueError("No models available")

# Example cache:
{
  "llama2": {"status": "loaded", "memory": 4096, "supported_tasks": ["rag", "summarization"]},
  "mistral": {"status": "loaded", "memory": 4096, "supported_tasks": ["rag"]},
  "neural-chat": {"status": "not_loaded", "memory": 2048, "supported_tasks": ["entity_extraction"]},
  "gemini-pro": {"status": "api_ready", "memory": None, "supported_tasks": ["rag", "summarization"]}
}
```

### 6.2 Ollama Integration

```python
# ollama_client.py - Wrapper for Ollama API

class OllamaClient:
    
    async def generate(
        self,
        model: str,
        prompt: str,
        system: str = "",
        temperature: float = 0.7,
        stream: bool = False
    ) -> str:
        """Generate text using local model"""
        
        url = f"{OLLAMA_URL}/api/generate"
        payload = {
            "model": model,
            "prompt": prompt,
            "system": system,
            "stream": stream,
            "options": {
                "temperature": temperature,
                "num_predict": 1000  # Max tokens
            }
        }
        
        try:
            if stream:
                # Stream response for real-time feedback
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, json=payload) as resp:
                        text = ""
                        async for line in resp.content:
                            chunk = json.loads(line)
                            text += chunk.get("response", "")
                            yield text
            else:
                # Wait for complete response
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, json=payload) as resp:
                        result = await resp.json()
                        return result.get("response", "")
        
        except ConnectionError:
            raise Exception(f"Could not connect to Ollama at {OLLAMA_URL}")
    
    async def embed(self, model: str, text: str) -> List[float]:
        """Generate embedding for text"""
        
        url = f"{OLLAMA_URL}/api/embed"
        payload = {
            "model": model,
            "input": text
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                result = await resp.json()
                return result.get("embeddings", [[]])[0]  # First embedding
```

### 6.3 Gemini Integration

```python
# gemini_service.py - Wrapper for Gemini API

GEMINI_MODEL_ID = "gemini-2.5-flash"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

async def generate(prompt: str, system: str = "") -> str:
    """Generate using Gemini API"""
    
    import google.generativeai as genai
    
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(GEMINI_MODEL_ID)
    
    try:
        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        response = model.generate_content(full_prompt)
        return response.text
    
    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        raise

# Fallback in main controller:
try:
    answer = await ollama.generate(model_name, prompt, system=system)
except Exception as e:
    logger.warning(f"Ollama failed: {e}, trying Gemini")
    answer = await gemini_service.generate(prompt, system=system)
```

---

## 7. Vector Database Operations

### 7.1 Chroma Configuration

```python
# chroma_client.py - Vector DB setup

from chromadb import Client
from chromadb.config import Settings

# Initialize Chroma
chroma_settings = Settings(
    chroma_db_impl="duckdb_parquet",  # Persistent storage
    persist_directory="/data/chroma",
    anonymized_telemetry=False
)

chroma = Client(settings=chroma_settings)

# Collections organized by project
def get_or_create_collection(project_id: int):
    collection_name = f"project_{project_id}"
    return chroma.get_or_create_collection(
        name=collection_name,
        metadata={"type": "project_documents"}
    )
```

### 7.2 Embedding & Retrieval

```python
async def embed_and_store_chunks(
    project_id: int,
    document_id: int,
    chunks: List[str]
):
    """Embed chunks and store in vector DB"""
    
    collection = get_or_create_collection(project_id)
    
    for chunk_index, chunk_text in enumerate(chunks):
        # Generate embedding
        embedding = await ollama.embed(
            settings.embed_model,
            chunk_text
        )
        
        # Store in Chroma
        collection.add(
            ids=[f"doc_{document_id}_chunk_{chunk_index}"],
            embeddings=[embedding],
            documents=[chunk_text],
            metadatas=[{
                "document_id": str(document_id),
                "chunk_index": str(chunk_index),
                "filename": filename
            }]
        )

async def retrieve_relevant_chunks(
    project_id: int,
    query: str,
    top_k: int = 6,
    document_id: Optional[int] = None
) -> List[dict]:
    """Retrieve chunks by semantic similarity"""
    
    collection = get_or_create_collection(project_id)
    
    # Embed query
    query_embedding = await ollama.embed(
        settings.embed_model,
        query
    )
    
    # Search
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        where={"document_id": str(document_id)} if document_id else None
    )
    
    # Format results
    chunks = []
    for i, chunk_text in enumerate(results["documents"][0]):
        chunks.append({
            "text": chunk_text,
            "metadata": results["metadatas"][0][i],
            "distance": results["distances"][0][i],  # 0=identical, 2=opposite
            "similarity": 1 - results["distances"][0][i]  # 0-1 range
        })
    
    return chunks
```

### 7.3 Similarity Calculation

```
Cosine Similarity Example:

Query:    "What are safety requirements?"     (embedded → [0.2, 0.5, ...])
Chunk 1:  "Safety requirements include..."   (embedded → [0.21, 0.48, ...])
Chunk 2:  "Budget allocation for Q1..."      (embedded → [0.1, 0.1, ...])

Similarity Chunk 1: ~0.99 (very similar)
Similarity Chunk 2: ~0.15 (not similar)

Distance values stored in Chroma:
- Distance Chunk 1: 0.01 (1 - 0.99)
- Distance Chunk 2: 0.85 (1 - 0.15)

Chroma returns top_k sorted by distance (ascending) = sorted by similarity (descending)
```

---

## 8. Deployment Architecture

### 8.1 Production Deployment

```
┌────────────────────────────────────────┐
│         DNS / Load Balancer            │
│         (Nginx / HAProxy)              │
└────────────────────────────────────────┘
           │           │
    ┌──────┘           └──────┐
    ▼                         ▼
┌─────────────┐       ┌─────────────┐
│  App Pod 1  │       │  App Pod 2  │
│  (FastAPI)  │       │  (FastAPI)  │
└─────────────┘       └─────────────┘
    │                     │
    └──────────┬──────────┘
               ▼
       ┌──────────────┐
       │  PostgreSQL  │
       │  Primary     │
       └──────────────┘
               │
       ┌───────┴────────┐
       ▼                ▼
    Replica 1       Replica 2
    
    ┌──────────────────────────┐
    │  Shared Services         │
    ├──────────────────────────┤
    │  Chroma Vector DB        │
    │  Ollama LLM Container    │
    │  Redis Cache (optional)  │
    └──────────────────────────┘
    
    ┌──────────────────────────┐
    │  Background Workers      │
    ├──────────────────────────┤
    │  Ingest Worker 1         │
    │  Ingest Worker 2         │
    │  Model Sync Service      │
    └──────────────────────────┘
```

### 8.2 Docker Compose (Development)

```yaml
version: '3.9'
services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql://user:pass@postgres:5432/doctel
      OLLAMA_URL: http://ollama:11434
      GEMINI_API_KEY: ${GEMINI_API_KEY}
    depends_on:
      - postgres
      - ollama
      - chroma
    volumes:
      - ./app:/app/app

  postgres:
    image: postgres:15
    environment:
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
      POSTGRES_DB: doctel
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  ollama:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    environment:
      OLLAMA_HOST: 0.0.0.0:11434

  chroma:
    image: ghcr.io/chroma-core/chroma:latest
    environment:
      IS_PERSISTENT: true
    volumes:
      - chroma_data:/chroma/data
    ports:
      - "8001:8000"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  ollama_data:
  chroma_data:
  redis_data:
```

### 8.3 Kubernetes Deployment (Optional)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: doctel-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: doctel-api
  template:
    metadata:
      labels:
        app: doctel-api
    spec:
      containers:
      - name: api
        image: doctel:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: doctel-secrets
              key: database-url
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
      - name: ollama-sidecar  # Or separate pod
        image: ollama:latest
        resources:
          requests:
            memory: "4Gi"
            cpu: "2"
```

---

## 9. Performance Optimization

### 9.1 Database Optimization

```sql
-- Key indexes for performance
CREATE INDEX idx_documents_project_id ON documents(project_id);
CREATE INDEX idx_documents_status ON documents(status);
CREATE INDEX idx_documents_created_at ON documents(created_at DESC);
CREATE INDEX idx_chunks_document_id ON chunks(document_id);
CREATE INDEX idx_chunks_embedding_id ON chunks(embedding_id);

-- Query optimization: Use EXPLAIN ANALYZE
EXPLAIN ANALYZE
SELECT d.*, da.executive_summary
FROM documents d
LEFT JOIN doc_analysis da ON d.id = da.document_id
WHERE d.project_id = 1 AND d.status = 'completed'
ORDER BY d.created_at DESC
LIMIT 50;

-- Connection pooling
sqlalchemy.pool.NullPool or
sqlalchemy.pool.QueuePool(pool_size=20, max_overflow=40)
```

### 9.2 API Response Caching

```python
from functools import lru_cache
from aiocache import cached, Cache

@cached(cache=Cache.MEMORY)  # In-memory cache with TTL
@app.get("/api/documents/{doc_id}/analysis")
async def get_document_analysis(doc_id: int):
    # Cache hit for repeated requests
    doc = await db.get_document(doc_id)
    return {"analysis": doc.analysis}

# Redis caching for distributed systems
from aiocache import Redis

@cached(cache=Cache.REDIS, ttl=3600)  # 1-hour cache
async def get_suggested_prompts(doc_id: int):
    return await db.get_prompts(doc_id)
```

### 9.3 Embedding Batch Processing

```python
async def batch_embed_chunks(chunks: List[str], batch_size=32):
    """Process chunks in batches for efficiency"""
    
    embeddings = []
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i+batch_size]
        
        # Embed entire batch at once
        batch_embeddings = await ollama.embed_batch(
            model=settings.embed_model,
            texts=batch
        )
        
        embeddings.extend(batch_embeddings)
        
        # Progress indication
        logger.info(f"Embedded {i+len(batch)}/{len(chunks)} chunks")
    
    return embeddings
```

### 9.4 Load Testing Parameters

```
Expected Scenario:
├─ 50 concurrent users
├─ 10 document uploads/minute
├─ 50 Q&A requests/minute
├─ Average response time: <5 seconds
├─ 99th percentile: <10 seconds

Load Testing (using Locust or k6):
├─ Gradual ramp-up: 10 → 100 users over 5 minutes
├─ Sustained: Hold at 100 users for 10 minutes
├─ Stress test: Increase to 200+ users to find breaking point
├─ Metrics: Response time, error rate, throughput

Success Criteria:
├─ p50 (median) response time < 3 seconds
├─ p99 (99th percentile) < 10 seconds
├─ Error rate < 0.1%
├─ Throughput > 100 requests/second
```

---

## 10. Scalability Considerations

### 10.1 Horizontal Scaling

```
Current: 1 App Server → 50 users

Scale to 500 users:
├─ Add load balancer (Nginx/HAProxy)
├─ Deploy 5-10 app instances
├─ Use connection pooling
├─ Implement caching layer (Redis)
├─ Database read replicas
└─ Monitor with observability stack

Bottleneck Analysis:
├─ If CPU bound → Add app instances
├─ If memory bound → Optimize queries, add caching
├─ If I/O bound (DB) → Read replicas, indexing
├─ If LLM bottleneck → Add Ollama instances or use Gemini
```

### 10.2 Vector Database Scaling

```
Current: Chroma in single container

Scale to millions of vectors:
├─ Option 1: Use Chroma Enterprise
├─ Option 2: Switch to Pinecone / Weaviate (managed)
├─ Option 3: Use PostgreSQL pgvector extension

Migration path:
1. Keep existing Chroma until 100K+ vectors
2. Plan migration to PG + pgvector
3. Test performance comparison
4. Migrate with zero downtime
```

### 10.3 LLM Scaling

```
Current: Single Ollama container (4GB RAM per model)

Scale options:
├─ Load balance across multiple Ollama instances
├─ Use Ollama clustering (if available)
├─ Add GPU acceleration for models
├─ Fallback to Gemini API for peak loads
├─ Implement model caching/quantization

Resource planning:
├─ llama2 (7B): 4GB RAM, CPU fallback
├─ llama2 (13B): 8GB RAM, GPU recommended
├─ Mistral: 7B model (efficient)
├─ Neural-chat: Lightweight, fast
```

### 10.4 Database Scaling

```
PostgreSQL setup:
├─ Primary (write) server
├─ 2+ Read replicas
├─ Connection pooling (PgBouncer)
├─ Partitioning for large tables

Partitioning strategy:
└─ chunks table (millions of rows)
   ├─ Partition by project_id
   ├─ Partition by time (monthly)
   └─ Hybrid: project_id + time

Example:
-- Monthly partitions by project
CREATE TABLE chunks_2026_05
PARTITION OF chunks
FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');
```

---

## Summary: Performance Targets

| Metric | Target | Current |
|--------|--------|---------|
| Concurrent Users | 100+ | ✓ |
| Doc Upload | 2-5 sec | ✓ |
| Analysis | 30-60 sec | ✓ |
| RAG Answer | 3-10 sec | ✓ |
| API p50 | <3 sec | ✓ |
| API p99 | <10 sec | ✓ |
| Uptime | 99.5% | Achievable |
| Supported Documents | 100K+ | With optimization |

---

**Document Version:** 1.0  
**Last Updated:** May 10, 2026  
**Next Review:** August 10, 2026

**Questions? Contact:** devops-team@zetdc.co.zw
