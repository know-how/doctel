# Functional Requirement Specification (FRS) Document
## DocIntel (DocTel) - Document Analysis & AI-Powered Insights System

**Version:** 1.0  
**Date:** May 10, 2026  
**Status:** Final  
**Organization:** ZETDC (Zimbabwe Electricity Transmission and Distribution Company)

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [System Architecture Overview](#system-architecture-overview)
3. [Functional Requirements Decomposition](#functional-requirements-decomposition)
4. [Data Flow & System Interactions](#data-flow--system-interactions)
5. [User Workflows](#user-workflows)
6. [Technical Integration Points](#technical-integration-points)
7. [Security & Access Control](#security--access-control)
8. [Performance Requirements](#performance-requirements)
9. [Error Handling & Recovery](#error-handling--recovery)
10. [Implementation Details](#implementation-details)

---

## 1. Executive Summary

### 1.1 Purpose

DocTel is an AI-powered document intelligence system designed to enable users to upload company documents (PDFs, DOCX, TXT), automatically analyze them using Large Language Models (LLMs), and generate:

1. **Executive Summaries** - Brief overviews of document content
2. **Detailed Analysis** - Key themes, entities, sentiment, action items
3. **Actionable Prompts** - Context-specific questions users can ask
4. **Interactive Chat Interface** - Ask custom questions and receive RAG-powered answers with citations

### 1.2 Key Stakeholders

- **System Administrators**: Manage system settings, user access, model configurations
- **Document Analysts**: Upload documents, analyze them, generate reports
- **Viewers**: Access analysis results and ask questions about documents
- **System Operators**: Monitor system health, ingestion pipeline, model performance

### 1.3 Target Environment

- **Backend**: FastAPI (Python) running on Linux/Windows
- **Frontend**: React + Vite with TypeScript
- **Mobile**: React Native (Expo)
- **LLM Integration**: Ollama (local models), Gemini API (cloud)
- **Storage**: SQLAlchemy ORM + Vector Database (Chroma)
- **Authentication**: Email OTP, Active Directory (optional)

---

## 2. System Architecture Overview

### 2.1 High-Level System Components

```
┌─────────────────────────────────────────────────────────────────┐
│                        Client Layer                              │
├─────────────────────────────────────────────────────────────────┤
│  Web Frontend (React)  │  Mobile App (React Native)  │ APIs    │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FastAPI Backend Layer                         │
├─────────────────────────────────────────────────────────────────┤
│  Authentication │ Document Controllers │ RAG Service            │
│  RBAC Service   │ Analysis Pipeline    │ Model Router           │
└─────────────────────────────────────────────────────────────────┘
                               │
                ┌──────────────┼──────────────┐
                ▼              ▼              ▼
         ┌──────────┐   ┌─────────────┐  ┌──────────┐
         │PostgreSQL│   │ Chroma DB   │  │ Ollama   │
         │ Database │   │(Embeddings) │  │(LLMs)    │
         └──────────┘   └─────────────┘  └──────────┘
                           │
                           ▼
                      ┌──────────────┐
                      │ Gemini API   │
                      │ (Optional)   │
                      └──────────────┘
```

### 2.2 Core Services

| Service | Purpose | Key Components |
|---------|---------|-----------------|
| **Authentication Service** | User identity verification & token management | Email OTP, AD Integration, Session Management |
| **Ingestion Service** | Document processing pipeline | File parsing, chunking, embedding generation |
| **RAG Service** | Retrieval-Augmented Generation for Q&A | Vector search, context retrieval, LLM integration |
| **Model Router** | Intelligent model selection | Fallback chains, performance optimization |
| **Bootstrap Service** | Initial system setup & auto-discovery | Model detection, database initialization |
| **Document Service** | Document CRUD operations | Metadata management, status tracking |
| **RBAC Service** | Role-based access control | Permission checking, project membership |

---

## 3. Functional Requirements Decomposition

### 3.1 Document Upload & Ingestion (FR-01 to FR-03)

#### FR-01: Multi-Format Document Support
**Requirement:** System accepts PDF, DOCX, and TXT files  
**Implementation:**
- Endpoint: `POST /api/documents/upload`
- Supported MIME types: `application/pdf`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document`, `text/plain`
- File validation: Size limit, hash verification (SHA256)
- Error handling: Reject unsupported formats with HTTP 422

```python
# Service: ingestion_service.py
def _validate_document_format(filename: str, mime_type: str) -> bool:
    """Validate document format before processing"""
    allowed = {'application/pdf', 'application/vnd.ms-word', 'text/plain'}
    return mime_type in allowed
```

**Data Stored:**
- Document metadata: `filename`, `mime_type`, `pages`, `sha256`, `path`
- Status tracking: `status` (uploaded→ingesting→embedded→summarized→completed)

---

#### FR-02: Document Metadata Assignment
**Requirement:** Users assign metadata during upload  
**Implementation:**
- Metadata fields:
  - `doc_type` - Policy, Report, Meeting Minutes, Technical Spec, etc.
  - `doc_date` - Date of document (ISO format)
  - `tags_json` - Array of user-defined tags
  - `project_id` - Associated project

**Endpoint:** `POST /api/documents/upload`  
**Request Schema:**
```json
{
  "file": "<binary>",
  "project_id": 1,
  "doc_type": "Policy",
  "doc_date": "2026-05-10",
  "tags": ["HSE", "Safety", "Compliance"]
}
```

---

#### FR-03: Secure Document Storage
**Requirement:** Documents stored securely in centralized repository  
**Implementation:**
- Database: PostgreSQL with `documents` table
- File Storage: Server file system (configurable via `settings.document_store_path`)
- Access Control: Verified via RBAC before retrieval
- Encryption: Data in transit (TLS), at rest (configurable)

---

### 3.2 Document Analysis (FR-04 to FR-09)

#### FR-04: Executive Summary Generation
**Requirement:** Auto-generate concise summary (up to 10 sentences)  
**Implementation:**
- **Trigger:** After successful document chunking and embedding
- **Process:**
  1. Extract top chunks using semantic search
  2. Send to LLM with summarization prompt
  3. Store in `DocAnalysis.executive_summary`
  4. Display in dashboard

```python
# Service: ingestion_service.py
async def _generate_executive_summary(
    db: AsyncSession,
    doc: Document,
    text_chunks: List[str],
    model: str
) -> str:
    """Generate 10-sentence executive summary"""
    prompt = """Summarize this document in exactly 10 sentences or fewer:
    
    {text}
    
    Focus on key points and actionable insights."""
    
    summary = await ollama.generate(model, prompt)
    return summary
```

---

#### FR-05: Detailed Summary Generation
**Requirement:** Generate structured summary with bullet points  
**Implementation:**
- Format: Markdown with sections
- Structure: Key Points → Themes → Findings → Recommendations
- Storage: `DocAnalysis.detailed_summary` (Text)
- LLM Prompt includes domain context (ZETDC terminology)

**Example Output:**
```markdown
## Key Points
- SCADA systems need firmware updates by Q3
- Three substations require HSE compliance review

## Themes
- System Infrastructure (35% of content)
- Regulatory Compliance (40% of content)
- Risk Management (25% of content)

## Findings
1. Aging equipment in Northern transmission line
2. Staff training requirements identified

## Recommendations
- Allocate budget for equipment replacement
- Schedule training sessions Q2 2026
```

---

#### FR-06: Entity Extraction
**Requirement:** Identify and display key entities (people, places, dates, concepts)  
**Implementation:**
- **Entities Captured:**
  - People: Names mentioned in document
  - Organizations: Department names, external entities
  - Dates: Important dates and deadlines
  - Locations: Specific sites, regions, facilities
  - Technical Terms: SCADA, transformers, feeders, substations

- **Storage:** `DocAnalysis.entities_json` (JSON array)
- **Extraction Method:** LLM-based NER using domain-specific prompts

```json
{
  "entities": [
    {
      "type": "PERSON",
      "value": "Mr. Simoyi",
      "context": "Department head"
    },
    {
      "type": "LOCATION",
      "value": "Harare Substation",
      "context": "Distribution hub"
    },
    {
      "type": "DATE",
      "value": "2026-07-15",
      "context": "Compliance deadline"
    }
  ]
}
```

---

#### FR-07: Sentiment Analysis
**Requirement:** Determine overall tone (Positive, Neutral, Negative, Urgent)  
**Implementation:**
- **Sentiment Categories:**
  - Positive: Optimistic tone, achievements, improvements
  - Neutral: Factual, informational content
  - Negative: Issues, problems, risks identified
  - Urgent: Time-sensitive matters, critical issues

- **Confidence Score:** 0-1 (stored with sentiment)
- **Storage:** `DocAnalysis.sentiment` (String)
- **Logic:** Multi-sentence analysis + aggregation

---

#### FR-08: Topic & Theme Extraction
**Requirement:** Extract and list key topics discussed  
**Implementation:**
- **Output Format:** Array of topics with relevance scores
- **Storage:** `DocAnalysis.topics_json` (JSON)
- **Extraction:** LLM identifies major themes + % of document

```json
{
  "topics": [
    {
      "topic": "Infrastructure Modernization",
      "relevance_score": 0.85,
      "mentions": 24,
      "key_points": ["Transformer upgrades", "SCADA replacement"]
    },
    {
      "topic": "HSE Compliance",
      "relevance_score": 0.72,
      "mentions": 18,
      "key_points": ["Safety protocols", "Equipment maintenance"]
    }
  ]
}
```

---

#### FR-09: Action Items & Decisions Identification
**Requirement:** Extract action items and decisions (especially for meeting minutes)  
**Implementation:**
- **Action Items:** Specific tasks with owner (if identified) and deadline
- **Decisions:** Conclusions, approvals, policy changes
- **Storage:** `DocAnalysis.action_items_json`, `DocAnalysis.decisions_json`

```json
{
  "action_items": [
    {
      "task": "Review SCADA firmware compatibility",
      "owner": "Mr. Simoyi",
      "deadline": "2026-06-30",
      "priority": "high",
      "status": "pending"
    }
  ],
  "decisions": [
    {
      "decision": "Approve budget allocation of $500K for equipment upgrade",
      "made_by": "Management Committee",
      "effective_date": "2026-05-15",
      "impact": "Infrastructure"
    }
  ]
}
```

---

### 3.3 Prompt Generation (FR-10 to FR-12)

#### FR-10: Automated Prompt Suggestion
**Requirement:** Generate 3-5 context-specific questions  
**Implementation:**
- **Trigger:** After analysis completion
- **Process:**
  1. Analyze document type, topics, entities
  2. Generate domain-appropriate questions
  3. Store in `SuggestedPrompt` table
  4. Display as interactive buttons in UI

- **Examples for Different Document Types:**
  - **Policy**: "What are the compliance requirements?", "Who is responsible for implementation?"
  - **Report**: "What are the key metrics?", "What are the recommended actions?"
  - **Meeting Minutes**: "What action items were assigned?", "What decisions were made?"

```python
# Service: rag_service.py
async def _generate_suggested_prompts(
    doc: Document,
    analysis: DocAnalysis,
    model: str
) -> List[str]:
    """Generate 3-5 context-specific prompts"""
    topics = json.loads(analysis.topics_json or "[]")
    doc_type = doc.doc_type or "document"
    
    prompt = f"""Based on this {doc_type} with topics {topics}, 
    generate exactly 4 specific, actionable questions a user might ask:
    1. 
    2. 
    3. 
    4. """
    
    response = await ollama.generate(model, prompt)
    # Parse and store suggestions
    return parse_suggestions(response)
```

**Stored Data:**
```sql
INSERT INTO suggested_prompts (document_id, prompt_text)
VALUES (123, 'What are the key infrastructure upgrades mentioned?');
```

---

#### FR-11: Custom Question Interface
**Requirement:** Free-text input field for user questions  
**Implementation:**
- **Endpoint:** `POST /api/documents/{doc_id}/ask`
- **Request:**
```json
{
  "question": "What are the safety protocols mentioned?",
  "session_id": "sess_abc123"
}
```
- **Validation:** Question length 10-500 characters, non-empty
- **Storage:** In `Message` table for chat history

---

#### FR-12: RAG-Powered Question Answering with Citations
**Requirement:** Retrieve relevant document sections and provide answers with source citations  
**Implementation:**

**Process Flow:**
1. **Embedding Generation:**
   - User question → Embedding vector (using `embed_model`)
   
2. **Vector Search:**
   - Query Chroma database with question embedding
   - Retrieve top-K relevant chunks (default K=6)
   - Score chunks by semantic relevance (distance)

3. **Context Assembly:**
   - Select top chunks with highest relevance
   - Include chunk citations and source references

4. **Answer Generation:**
   - Send system prompt + context + question to LLM
   - System prompt instructs model to cite sources
   - Model generates answer with in-line citations

5. **Response Formatting:**
   - Answer text with embedded citations
   - Citation format: `[Doc: filename, chunk N]`
   - Cross-references list at bottom

**Implementation Code:**
```python
# Service: rag_service.py
async def get_rag_answer_scoped(
    project_ids: List[int],
    user_query: str,
    db: AsyncSession,
    document_id: Optional[int] = None,
    model_name: Optional[str] = None,
    force_policy: bool = False,
    force_diagram: bool = False
) -> dict:
    """Generate RAG answer with citations"""
    
    # Step 1: Embed question
    query_embedding = await ollama.embed(settings.embed_model, user_query)
    
    # Step 2: Search vectors
    results_rows = []
    for pid in project_ids:
        res = chroma.query(str(pid), query_embedding, top_k=6, where={"document_id": document_id})
        # Parse results with citations
        for text, meta, distance in zip(docs, metas, distances):
            results_rows.append({
                "filename": meta.get("filename"),
                "chunk_index": meta.get("chunk_index"),
                "text": text,
                "distance": distance
            })
    
    # Step 3: Build citations and context
    citations = [{"filename": r["filename"], "chunk_index": r["chunk_index"]} 
                 for r in results_rows]
    context = "\n\n".join([r["text"] for r in results_rows])
    
    # Step 4: Generate answer
    system_prompt = "You are DocTel, an AI analyst. Use ONLY provided context. Always cite sources."
    user_prompt = f"Question: {user_query}\n\nContext:\n{context}"
    
    answer_text = await ollama.generate(model_name, user_prompt, system=system_prompt)
    
    # Step 5: Return with citations
    return {
        "answer_text": answer_text,
        "citations": citations,
        "used_model": model_name
    }
```

**Example Response:**
```json
{
  "answer_text": "According to the policy documents, there are three key safety protocols: (1) Pre-shift equipment inspection [Doc: HSE_Policy_2026.pdf, chunk 5], (2) Incident reporting procedures [Doc: HSE_Policy_2026.pdf, chunk 7], and (3) Emergency shutdown protocols [Doc: Emergency_Procedures.docx, chunk 3].",
  "citations": [
    {"filename": "HSE_Policy_2026.pdf", "chunk_index": 5, "text": "Pre-shift equipment inspection must be completed..."},
    {"filename": "HSE_Policy_2026.pdf", "chunk_index": 7, "text": "Incident reporting procedures..."},
    {"filename": "Emergency_Procedures.docx", "chunk_index": 3, "text": "Emergency shutdown protocols..."}
  ],
  "used_model": "llama2"
}
```

---

## 4. Data Flow & System Interactions

### 4.1 Document Ingestion Data Flow

```
[User Upload Document]
        ↓
[Validate Format & Size]
        ↓
[Store in Database] → Document record with status='uploaded'
        ↓
[Extract Text from File]
   ├── PDF → PyPDF2
   ├── DOCX → python-docx
   └── TXT → Direct read
        ↓
[Split into Chunks] (500-1000 tokens per chunk with overlap)
        ↓
[Generate Embeddings] (using embed_model)
        ↓
[Store in Vector DB] (Chroma)
        ↓
[Update Status] → status='embedded', ingest_percent=50
        ↓
[Generate Analysis]
   ├── Executive Summary
   ├── Detailed Summary
   ├── Entity Extraction
   ├── Sentiment Analysis
   ├── Topic Extraction
   └── Action Items
        ↓
[Generate Suggested Prompts] (3-5 context-specific questions)
        ↓
[Update Status] → status='completed', analysis_ready=true
        ↓
[Notify User] → Document ready for Q&A
```

### 4.2 Question Answering Data Flow

```
[User Asks Question]
        ↓
[Validate Question]
        ↓
[Create Embedding] of question
        ↓
[Search Vector DB] with embedding
        ↓
[Retrieve Top Chunks] (K=6, sorted by relevance)
        ↓
[Build Context] from chunks
        ↓
[Select LLM] (model_router logic)
        ↓
[Generate Answer]
   ├── Via Ollama (local)
   └── Via Gemini (cloud, if configured)
        ↓
[Extract Citations] from answer
        ↓
[Store in Chat History]
        ↓
[Return to User] with answer + citations
```

---

## 5. User Workflows

### 5.1 Workflow: Upload and Analyze Document

**User Role:** Document Analyst  
**Time to Complete:** 2-3 minutes upload + 15-30 seconds processing

**Steps:**
1. **Navigate to Upload Screen**
   - Click "Upload Document" button
   - Or drag-and-drop document onto interface

2. **Select File and Enter Metadata**
   - Choose PDF/DOCX/TXT file
   - Select or create project
   - Set document type (Policy, Report, etc.)
   - Add optional tags
   - Click "Upload"

3. **Monitor Processing**
   - View progress bar (Extracting → Chunking → Embedding → Summarizing)
   - Real-time status updates
   - ETA displayed

4. **View Analysis Dashboard**
   - Executive summary displayed
   - Key insights section shows:
     - Sentiment
     - Top entities
     - Main themes
     - Action items (if any)
   - "Ready to ask questions" confirmation

5. **Access Suggested Prompts**
   - See 3-5 pre-generated questions
   - Click any prompt to auto-submit question

---

### 5.2 Workflow: Ask Questions about Document

**User Role:** Any user with document access  
**Time to Complete:** 5-10 seconds per question

**Steps:**
1. **Open Document Analysis View**
   - Click on document from project list
   - System shows analysis dashboard on left, Q&A interface on right

2. **Ask Question (Two Options)**
   
   **Option A - Click Suggested Prompt:**
   - Click one of the 3-5 suggested question buttons
   - System auto-populates chat input
   - Presses Enter automatically

   **Option B - Type Custom Question:**
   - Click text input box "Ask a question about this document..."
   - Type custom question (min 10 chars, max 500 chars)
   - Press Enter or click Send

3. **System Processes Question**
   - Converts question to embedding
   - Searches vector database
   - Retrieves most relevant chunks
   - Generates answer via LLM

4. **View Answer with Citations**
   - Answer appears in chat bubble
   - Citations highlighted inline: `[Doc: filename, chunk N]`
   - Hover over citation to see source text
   - "Sources" section at bottom lists all references

5. **Continue Conversation**
   - Ask follow-up questions
   - View chat history for session
   - Each Q&A logged and stored

---

### 5.3 Workflow: Project-Level Analysis

**User Role:** Project Manager / Analyst  
**Time to Complete:** 5-10 minutes

**Steps:**
1. **Create or Select Project**
   - Project groups related documents
   - All documents in project indexed together

2. **Upload Multiple Documents**
   - Upload 3+ related documents (e.g., all Q1 reports)
   - System processes in parallel or queue

3. **Ask Cross-Document Questions**
   - Scope: "project" instead of "document"
   - Example: "Compare budget allocations across all reports"
   - System searches all project documents
   - Returns aggregated answer with multiple citations

4. **Generate Cross-Document Report**
   - Select multiple documents
   - Click "Generate Comparison Report"
   - System creates markdown or PDF with findings

---

## 6. Technical Integration Points

### 6.1 API Endpoints

#### Document Management
```
POST   /api/documents/upload              - Upload new document
GET    /api/documents/{doc_id}            - Get document details
DELETE /api/documents/{doc_id}            - Delete document
GET    /api/documents/{doc_id}/analysis   - Get analysis results
```

#### Question Answering
```
POST   /api/documents/{doc_id}/ask        - Ask question about document
POST   /api/projects/{proj_id}/ask        - Ask cross-document question
GET    /api/sessions/{sess_id}/messages   - Get chat history
```

#### Project Management
```
POST   /api/projects                      - Create project
GET    /api/projects                      - List user's projects
GET    /api/projects/{proj_id}            - Get project details
PUT    /api/projects/{proj_id}            - Update project
DELETE /api/projects/{proj_id}            - Delete project
```

#### Model Management
```
GET    /api/models/available              - List available models
POST   /api/models/select                 - Select active model
GET    /api/models/status                 - Get model status
```

---

### 6.2 Database Schema Integration

**Key Tables:**
```
users
  ├─ id (PK)
  ├─ username (unique)
  ├─ email
  ├─ role (admin, analyst, viewer)
  └─ created_at

projects
  ├─ id (PK)
  ├─ name
  ├─ owner_user_id (FK → users)
  ├─ created_at
  └─ documents[] (1-to-many)

documents
  ├─ id (PK)
  ├─ project_id (FK → projects)
  ├─ filename
  ├─ mime_type
  ├─ sha256 (for dedup)
  ├─ status (uploaded|ingesting|completed|failed)
  ├─ ingest_percent (0-100)
  ├─ analysis_ready (boolean)
  ├─ created_at
  └─ analysis (1-to-1) → doc_analysis

doc_analysis
  ├─ id (PK)
  ├─ document_id (FK → documents)
  ├─ executive_summary (text)
  ├─ detailed_summary (text)
  ├─ sentiment (string)
  ├─ entities_json (JSON)
  ├─ topics_json (JSON)
  └─ action_items_json (JSON)

chunks
  ├─ id (PK)
  ├─ document_id (FK → documents)
  ├─ chunk_index
  ├─ text (content)
  ├─ citation_ref
  └─ embedding_id (FK → embeddings)

embeddings
  ├─ id (PK)
  ├─ vector_ref (Chroma ID)
  └─ created_at

suggested_prompts
  ├─ id (PK)
  ├─ document_id (FK → documents)
  ├─ prompt_text
  └─ created_at

sessions
  ├─ id (PK)
  ├─ session_uuid (unique)
  ├─ project_id (FK → projects)
  ├─ document_id (FK → documents)
  ├─ user_id (FK → users)
  ├─ model_name
  └─ created_at

messages
  ├─ id (PK)
  ├─ session_id (FK → sessions)
  ├─ role (user|assistant)
  ├─ content (text)
  ├─ citations_json (JSON)
  └─ created_at
```

---

### 6.3 LLM Service Integration

#### Model Selection Logic
```
Input: task_type (e.g., 'summarization', 'rag', 'entity_extraction')

1. Check if user has forced a specific model → use it
2. Check if model is currently active → use it
3. Load model_cache.json (list of available models)
4. Apply fallback chain:
   - Preferred model for task
   - Secondary model (if preferred unavailable)
   - Default model (generic)
5. Return selected model name

Output: model_name (e.g., 'llama2', 'mistral')
```

#### Vector Embedding Process
```
Input: text_chunk (500-1000 tokens)

1. Send to embedding model (e.g., 'nomic-embed-text')
2. Receive embedding vector (384-1536 dimensions)
3. Store in Chroma with metadata:
   {
     "document_id": 123,
     "chunk_index": 5,
     "filename": "document.pdf"
   }
4. Store vector ID in embeddings table

Output: embedding_id (reference for later retrieval)
```

#### LLM Generation Process
```
Input: prompt, system_prompt, model_name

1. If model == GEMINI:
   - Call Gemini API with prompt
   - Handle API rate limits and errors
   - Return response text
   
2. Else (local Ollama):
   - Stream request to Ollama
   - Aggregate streamed chunks
   - Return response text

Output: generated_text
```

---

## 7. Security & Access Control

### 7.1 Authentication Methods

#### Email OTP (Primary)
```
1. User enters email
2. System generates 6-digit OTP
3. OTP sent via email (SMTP)
4. User enters OTP
5. System creates auth token
6. Token valid for 24 hours
```

#### Active Directory (Optional)
```
1. User submits AD credentials
2. System queries AD server
3. Credentials validated
4. User profile loaded/created
5. Auth token issued
```

### 7.2 Authorization & RBAC

**Role Hierarchy:**
```
admin
├─ Manage all projects
├─ Manage users
├─ Configure system settings
├─ View audit logs
└─ Full API access

analyst
├─ Create/view projects
├─ Upload documents
├─ Ask questions about documents
└─ Export analysis results

viewer
├─ View projects (shared)
├─ View analysis results
├─ Ask questions
└─ No upload/delete permissions
```

**Access Control Rules:**
```python
# Decorator-based access control
@require_role("analyst")  # Only analysts and admins
async def upload_document(file: UploadFile):
    pass

@check_project_access(project_id)  # User must be project member
async def view_project_documents(project_id: int):
    pass
```

### 7.3 Data Security

- **Encryption in Transit:** TLS 1.3 for all API communications
- **Encryption at Rest:** Optional database encryption (configurable)
- **File Storage:** Documents stored outside web root, access verified
- **API Keys:** Gemini API key stored in environment, never logged
- **Session Management:** Token-based, short-lived (24 hours default)
- **Audit Logging:** All document access logged with timestamp, user, action

---

## 8. Performance Requirements

### 8.1 Processing Performance

| Operation | Target Time | Notes |
|-----------|------------|-------|
| Upload 10-page PDF | 2-5 sec | File transfer + metadata storage |
| Extract text from PDF | 3-10 sec | Depends on file complexity |
| Generate embeddings | 10-20 sec | Per 10 chunks (~5K tokens) |
| Executive summary | 5-15 sec | LLM generation time |
| Complete analysis | 30-60 sec | Total for 10-page document |
| RAG answer generation | 3-10 sec | Vector search + LLM generation |

### 8.2 Scalability

- **Concurrent Users:** Support 100+ concurrent users
- **Document Concurrent Processing:** 5 documents ingesting simultaneously
- **Vector DB:** Support 100K+ chunks without performance degradation
- **Chat History:** Scale to 1000+ messages per session

### 8.3 API Response Times

```
GET /api/documents/{doc_id}                  < 100ms
POST /api/documents/{doc_id}/ask             < 10s (includes LLM time)
GET /api/projects                            < 200ms
GET /api/sessions/{sess_id}/messages         < 300ms
```

---

## 9. Error Handling & Recovery

### 9.1 Document Processing Errors

```
Error: Unsupported file format
├─ HTTP Status: 422
├─ Error Message: "PDF, DOCX, and TXT files supported"
└─ Recovery: Suggest file conversion

Error: Embedding generation failed
├─ HTTP Status: 500
├─ Error Message: "Analysis failed. Retrying..."
└─ Recovery: Auto-retry up to 3 times, then queue for later

Error: LLM model unavailable
├─ HTTP Status: 503
├─ Error Message: "Current model unavailable"
└─ Recovery: Fallback to next model in chain, or queue for retry

Error: Vector DB connection lost
├─ HTTP Status: 503
├─ Error Message: "Service temporarily unavailable"
└─ Recovery: Wait 5sec, retry, or use cache if available
```

### 9.2 Chat & RAG Errors

```
Error: No relevant chunks found
├─ HTTP Status: 200 (success, but...)
├─ Response: "I couldn't find information about that in the document. Try rephrasing your question."
└─ Recovery: Suggest broader questions, list available topics

Error: Question malformed
├─ HTTP Status: 422
├─ Error Message: "Question must be 10-500 characters"
└─ Recovery: Client-side validation prevents this

Error: Document not found
├─ HTTP Status: 404
├─ Error Message: "Document {doc_id} not found or access denied"
└─ Recovery: List available documents for user
```

### 9.3 Database Connection Errors

```
Automatic Retry Logic:
├─ Attempt 1: Immediate retry
├─ Attempt 2: Retry after 2 seconds
├─ Attempt 3: Retry after 5 seconds
└─ If all fail: Return 503, log error, alert admin
```

---

## 10. Implementation Details

### 10.1 Technology Stack Summary

| Component | Technology | Version |
|-----------|-----------|---------|
| Backend Framework | FastAPI | 0.95+ |
| Language | Python | 3.10+ |
| Database | PostgreSQL | 14+ |
| ORM | SQLAlchemy | 2.0+ |
| Vector DB | Chroma | Latest |
| LLM Runtime | Ollama | Latest |
| Cloud LLM | Gemini API | Latest |
| Frontend | React + Vite | React 18, Vite 4 |
| Mobile | React Native | Expo SDK 50+ |
| Auth | Email OTP, AD | Custom + LDAP |

### 10.2 Configuration Management

**Key Configuration Parameters:**
```yaml
# app/config.yaml
embedding:
  model: nomic-embed-text
  dimensions: 384

llm:
  preferred_model: llama2
  fallback_models: [mistral, neural-chat]
  temperature: 0.7
  top_k: 6

processing:
  chunk_size: 1000
  chunk_overlap: 200
  max_file_size_mb: 100
  concurrent_jobs: 5

security:
  token_expiry_hours: 24
  otp_validity_minutes: 15
  enable_encryption: true

performance:
  embedding_batch_size: 32
  vector_search_top_k: 6
```

### 10.3 Deployment Architecture

```
┌─────────────────────────────────┐
│     Load Balancer (Nginx)       │
└──────────────┬──────────────────┘
               │
     ┌─────────┴─────────┐
     ▼                   ▼
┌──────────┐        ┌──────────┐
│ App #1   │        │ App #2   │
│(FastAPI) │        │(FastAPI) │
└──┬────┬──┘        └──┬────┬──┘
   │    │               │    │
   │    └───────┬───────┘    │
   │            ▼            │
   │      ┌──────────────┐   │
   │      │  PostgreSQL  │   │
   │      │  Database    │   │
   │      └──────────────┘   │
   │            │            │
   │    ┌───────┴────────┐   │
   └──→ │  Ingest Worker │   │
        │  (Background)  │   │
        └───────┬────────┘   │
                ▼            │
          ┌──────────────┐   │
          │ Chroma Vector│   │
          │ Database     │   │
          └──────────────┘   │
                │            │
                │     ┌──────┴──┐
                │     ▼         ▼
                │  ┌──────┐  ┌──────┐
                │  │Ollama│  │Gemini│
                └→ │LLMs  │  │API   │
                   └──────┘  └──────┘
```

---

## 11. Future Enhancements

### Phase 2 Capabilities
- **Multi-file Analysis**: Simultaneous analysis of 10+ documents
- **Advanced Diagramming**: Auto-generate flowcharts, network diagrams
- **Policy Generation**: AI-assisted policy draft creation
- **Report Generation**: Automated multi-document reports
- **Search Across All Documents**: Global search with faceted filtering
- **Document Comparison**: Side-by-side comparison with diffs

### Phase 3 Capabilities
- **Fine-tuned Models**: Domain-specific model training for ZETDC
- **Workflow Automation**: Approval workflows for policy drafts
- **Integration APIs**: Salesforce, SharePoint, Slack integration
- **Mobile App**: Full-featured React Native mobile application
- **Offline Mode**: Download documents for offline access

---

## 12. Conclusion

DocTel (DocIntel) is a comprehensive document intelligence system that leverages modern AI and NLP techniques to dramatically improve how organizations manage and extract value from their document repositories.

**Key Achievements:**
✓ Automated document analysis with 3-5 actionable prompts per document  
✓ RAG-powered Q&A with source citations  
✓ Multi-format support (PDF, DOCX, TXT)  
✓ Role-based access control for enterprise security  
✓ Fast processing (30-60 seconds per document)  
✓ Cross-document analysis within projects  
✓ Local LLM support + cloud fallback  

**Expected Business Impact:**
- Reduce document review time by 70%
- Improve information discovery by 90%
- Enable faster decision-making
- Improve compliance and audit trails
- Support knowledge preservation

---

**Document Version History:**

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-05-10 | System Design | Initial FRS document |

**Approval Sign-offs:**

| Role | Name | Signature | Date |
|------|------|-----------|------|
| Technical Lead | | | |
| Project Manager | | | |
| Stakeholder | | | |

---

**End of Functional Requirements Specification Document**
