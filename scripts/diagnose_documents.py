#!/usr/bin/env python3
"""
Document Ingestion Diagnostic Script

This script diagnoses why specific documents fail to produce chunks.
Run this to investigate documents 9 and 10 vs the working Dunning Manual.

Usage:
    .venv\Scripts\python scripts\diagnose_documents.py
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, func
from app.db.database import AsyncSessionLocal
from app.db.models import Document, Chunk, Embedding, DocAnalysis
from app.services.ingestion_service import extract_text, chunk_text
from PyPDF2 import PdfReader


async def diagnose_document(doc_id: int):
    """Run comprehensive diagnostic on a single document."""
    print(f"\n{'='*70}")
    print(f"DIAGNOSTIC REPORT: Document ID {doc_id}")
    print(f"{'='*70}")
    
    async with AsyncSessionLocal() as db:
        # Get document
        result = await db.execute(select(Document).where(Document.id == doc_id))
        doc = result.scalar_one_or_none()
        
        if not doc:
            print(f"❌ Document {doc_id} NOT FOUND in database")
            return
        
        print(f"\n📄 DOCUMENT METADATA:")
        print(f"  filename: {doc.filename}")
        print(f"  mime_type: {doc.mime_type}")
        print(f"  detected_type: {doc.detected_type}")
        print(f"  status: {doc.status}")
        print(f"  ingest_step: {doc.ingest_step}")
        print(f"  ingest_percent: {doc.ingest_percent}")
        print(f"  ingest_message: {doc.ingest_message}")
        print(f"  error_message: {doc.error_message or '(none)'}")
        print(f"  path: {doc.path}")
        
        # Check file
        print(f"\n📁 FILE CHECK:")
        if not doc.path:
            print(f"  ❌ No file path stored")
        elif not os.path.exists(doc.path):
            print(f"  ❌ File does not exist at path")
        else:
            size = os.path.getsize(doc.path)
            print(f"  ✓ File exists")
            print(f"  size: {size} bytes ({size/1024:.2f} KB)")
            
            # Try PDF extraction analysis
            if doc.path.lower().endswith('.pdf'):
                print(f"\n📄 PDF ANALYSIS:")
                try:
                    reader = PdfReader(doc.path)
                    page_count = len(reader.pages)
                    print(f"  page_count: {page_count}")
                    
                    # Extract text from first few pages
                    total_text = ""
                    for i, page in enumerate(reader.pages[:5]):
                        text = page.extract_text() or ""
                        total_text += text
                        print(f"  Page {i+1}: {len(text)} characters")
                    
                    print(f"  Total extracted (first 5 pages): {len(total_text)} characters")
                    
                    if len(total_text.strip()) < 50:
                        print(f"  ⚠️ WARNING: Very little text extracted!")
                        print(f"  This PDF may be:")
                        print(f"    - Image-based (scanned) without OCR")
                        print(f"    - Password protected")
                        print(f"    - Corrupted or malformed")
                        print(f"    - Using non-standard encoding")
                        
                except Exception as e:
                    print(f"  ❌ PDF parsing error: {e}")
        
        # Check chunks
        print(f"\n🧩 CHUNK ANALYSIS:")
        chunk_result = await db.execute(
            select(func.count(Chunk.id)).where(Chunk.document_id == doc_id)
        )
        chunk_count = chunk_result.scalar() or 0
        print(f"  chunks in database: {chunk_count}")
        
        if chunk_count > 0:
            chunk_res = await db.execute(
                select(Chunk).where(Chunk.document_id == doc_id).limit(3)
            )
            for c in chunk_res.scalars():
                print(f"    Chunk {c.chunk_index}: {len(c.text)} characters")
        else:
            print(f"  ❌ NO CHUNKS FOUND")
            
            # Check if document status suggests it was processed
            if doc.status in ("completed", "summarized", "embedded"):
                print(f"  ⚠️ Document status is '{doc.status}' but no chunks exist!")
                print(f"    This indicates chunking failed silently.")
            elif doc.status == "failed":
                print(f"  ℹ️ Document status is 'failed' - check error_message above")
            elif doc.status == "uploaded":
                print(f"  ℹ️ Document status is 'uploaded' - ingestion never started")
        
        # Check embeddings
        print(f"\n🔢 EMBEDDING ANALYSIS:")
        emb_result = await db.execute(
            select(func.count(Embedding.id)).where(
                Embedding.id.in_(
                    select(Chunk.embedding_id).where(Chunk.document_id == doc_id)
                )
            )
        )
        emb_count = emb_result.scalar() or 0
        print(f"  embeddings: {emb_count}")
        print(f"  embedding_provider: {doc.embedding_provider or '(null)'}")
        print(f"  embedding_model: {doc.embedding_model or '(null)'}")
        print(f"  embedding_version: {doc.embedding_version or '(null)'}")
        print(f"  embedded_at: {doc.embedded_at or '(null)'}")
        
        # Check analysis
        print(f"\n📊 ANALYSIS:")
        analysis_result = await db.execute(
            select(DocAnalysis).where(DocAnalysis.document_id == doc_id)
        )
        analysis = analysis_result.scalar_one_or_none()
        if analysis:
            print(f"  ✓ DocAnalysis exists")
            print(f"    executive_summary length: {len(analysis.executive_summary) if analysis.executive_summary else 0}")
            print(f"    entities: {len(analysis.entities_json) if analysis.entities_json else 0} chars")
        else:
            print(f"  ❌ No DocAnalysis found")
        
        # Summary diagnosis
        print(f"\n🔍 DIAGNOSIS:")
        if chunk_count == 0:
            if doc.status == "failed":
                print(f"  ❌ Ingestion FAILED at step: {doc.ingest_step}")
                print(f"     Error: {doc.error_message}")
            elif doc.status in ("uploaded",):
                print(f"  ⏳ Document was uploaded but ingestion never started")
                print(f"     Check if ingest worker is running")
            elif doc.ingest_step == "extract":
                print(f"  ❌ Text EXTRACTION failed")
                print(f"     The PDF likely contains no extractable text layer")
                print(f"     Try: Check if PDF is image-based and needs OCR")
            else:
                print(f"  ❌ CHUNK CREATION failed at step: {doc.ingest_step}")
                print(f"     Text may have been extracted but chunking produced nothing")
        else:
            print(f"  ✓ Document appears healthy with {chunk_count} chunks")
        
        print(f"\n{'='*70}\n")


async def test_extraction_directly(file_path: str):
    """Test text extraction directly on a file."""
    print(f"\n🧪 DIRECT EXTRACTION TEST: {file_path}")
    print(f"{'='*70}")
    
    if not os.path.exists(file_path):
        print(f"❌ File not found: {file_path}")
        return
    
    print(f"File size: {os.path.getsize(file_path)} bytes")
    
    # Try PyPDF2 extraction
    print(f"\n📄 PyPDF2 extraction:")
    try:
        reader = PdfReader(file_path)
        print(f"Pages: {len(reader.pages)}")
        
        all_text = ""
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            all_text += text
            if i < 3:
                print(f"  Page {i+1}: {len(text)} chars")
                if text.strip():
                    preview = text.strip()[:100].replace('\n', ' ')
                    print(f"    Preview: {preview}...")
        
        print(f"\nTotal extracted: {len(all_text)} characters")
        print(f"Stripped: {len(all_text.strip())} characters")
        
        # Test chunking
        if all_text.strip():
            print(f"\n🧩 Testing chunk_text():")
            chunks = chunk_text(all_text, chunk_size=1000, chunk_overlap=150)
            chunks = [c.strip() for c in chunks if c.strip()]
            print(f"  Produced {len(chunks)} chunks")
            if chunks:
                print(f"  First chunk: {len(chunks[0])} characters")
        else:
            print(f"\n⚠️ No text to chunk!")
            
    except Exception as e:
        print(f"❌ Extraction error: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"{'='*70}\n")


async def main():
    """Main diagnostic runner."""
    print("\n" + "="*70)
    print("DOCUMENT INGESTION DIAGNOSTIC TOOL")
    print("="*70)
    
    # Document IDs to investigate
    doc_ids = [9, 10]  # Failing documents
    dunning_manual_id = 2  # Working document (assuming ID 2 based on earlier context)
    
    # Diagnose each document
    for doc_id in doc_ids:
        await diagnose_document(doc_id)
    
    # Also check working document for comparison
    print(f"\n{'='*70}")
    print("COMPARISON: Working Document (Dunning Manual)")
    print(f"{'='*70}")
    await diagnose_document(2)
    
    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    print("""
If Document 9 and 10 show:
  - File exists ✓
  - 0 chunks ❌
  - Status = completed or embedded
  - No error message

Then the issue is: TEXT EXTRACTION PRODUCED EMPTY TEXT

Root causes:
  1. PDF is image-based (scanned) without OCR text layer
  2. PDF uses non-standard encoding PyPDF2 cannot read
  3. PDF is password-protected
  4. File corruption

Next steps:
  1. Check if tesseract OCR is installed: tesseract --version
  2. Check if pypdfium2 is installed: pip show pypdfium2
  3. Try opening the PDF in a text editor to see if it has extractable text
  4. Use the /api/ingest/diagnostic/{doc_id} endpoint for web-based diagnostics
""")


if __name__ == "__main__":
    asyncio.run(main())
