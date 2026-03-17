# DocIntel: Local & Privacy-First Document Intelligence Assistant

## Overview
DocIntel is a comprehensive document intelligence solution designed for local, offline operation on Windows 11. It provides high-performance document ingestion, analysis, and a Retrieval-Augmented Generation (RAG) assistant while ensuring company data never leaves the local machine.

## Core Architecture
The system is built with a focus on privacy and performance on standard hardware (e.g., 16 GB RAM, CPU-only).

### 1. Local AI Runtime
- **Engine**: [Ollama](https://ollama.com/) (Windows)
- **Text Models**:
  - `llama3.2:8b-instruct` (Primary)
  - `llama3.2:3b-instruct` (Performance Fallback)
- **Vision Model**: `llava:7b` (for image analysis and OCR fallback)
- **Embedding Model**: `nomic-embed-text` (for high-speed vector search)

### 2. Ingestion Pipeline
DocIntel supports a variety of formats including **PDF, DOCX, TXT, PNG, and JPG**.
- **Extraction**: Uses `PyPDF2` and `python-docx` for structured text.
- **OCR**: Integrated `Tesseract` support for scanned documents and images.
- **Processing**: Features a parallelized pipeline using `asyncio.gather` to meet performance targets (≤ 15s for a 10-page PDF).
- **Analysis**: Automatically generates executive/detailed summaries, identifies entities (people, orgs, dates), detects sentiment, and proposes document-specific prompts.

### 3. RAG & Intelligence
- **Vector Database**: [Chroma DB](file:///c:/Users/ze9167523/IdeaProjects/doctel/app/utils/chroma_client.py) for persistent local vector storage.
- **Metadata Storage**: [SQLite](file:///c:/Users/ze9167523/IdeaProjects/doctel/app/db/database.py) for structured project and session data.
- **Grounded Q&A**: Answers are synthesized strictly from retrieved document chunks with hoverable citations `[Doc: filename, chunk/page]`.
- **Process Flows**: Capable of generating numbered steps, Mermaid flowchart code, and drawing prompts for visualization.

## Security & RBAC
- **Local-Only**: Backend is bound to `127.0.0.1`. No outbound API calls are made during inference.
- **RBAC**: Role-Based Access Control with `admin`, `analyst`, and `viewer` roles.
- **Data Protection**: Supports Windows EFS for directory encryption and SHA-256 for file deduplication.

## Directory Structure
The application is deployed at `C:\LocalAI\`:
- `app/`: [FastAPI backend](file:///c:/Users/ze9167523/IdeaProjects/doctel/app/main.py) and core services.
- `data/`: Uploads, OCR cache, and Chroma collections.
- `db/`: SQLite database file (`app.db`).
- `scripts/`: PowerShell automation scripts.

## Operations Manual

### Setup
Run the setup script to initialize folders, install Python dependencies, and pull models:
```powershell
powershell ./scripts/setup.ps1
```

### Running the System
Start the Ollama service and the FastAPI server:
```powershell
powershell ./scripts/run.ps1
```
The API will be available at `http://127.0.0.1:8000`.

### Document Ingestion
Perform bulk ingestion for a specific project:
```powershell
powershell ./scripts/ingest.ps1 -Project "ProjectName" -Path "C:\Path\To\Docs"
```

### Backup
Create a timestamped ZIP backup of your local data and database:
```powershell
powershell ./scripts/backup.ps1
```

## Performance & Optimization
- **Parallelism**: Ingestion steps (extraction, chunking, embedding) overlap to maximize CPU utilization.
- **Memory Management**: The system ensures only one heavy model (Text vs. Vision) is active in memory to stay within the 16 GB RAM limit.
- **Configuration**: Fine-tune models and thresholds in [config.yaml](file:///c:/Users/ze9167523/IdeaProjects/doctel/app/config.yaml).
