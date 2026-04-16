"""
training_export_service.py – Export ingested documents as training data (JSONL format).

Converts DocAnalysis and Chunks into instruction/input/output tuples suitable for
LoRA fine-tuning. Each example represents how we want the model to analyze documents.
"""
import json
import logging
from pathlib import Path
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models import Document, Chunk, DocAnalysis
from app.config import settings

logger = logging.getLogger(__name__)


async def export_documents_for_training(
    project_ids: List[int],
    output_dir: Optional[str] = None,
    db: Optional[AsyncSession] = None,
) -> str:
    """
    Export documents and their analyses as JSONL training data.
    
    Args:
        project_ids: List of project IDs to export
        output_dir: Directory to save training batch (defaults to settings.base_dir/training/batches)
        db: AsyncSession for database queries
    
    Returns:
        Path to generated JSONL file
    
    Raises:
        ValueError: If output_dir doesn't exist or cannot be created
    """
    if db is None:
        from app.db.database import AsyncSessionLocal
        db = AsyncSessionLocal()
    
    if output_dir is None:
        output_dir = str(Path(settings.base_dir) / "training" / "batches")
    
    # Ensure output directory exists
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Query all documents in specified projects with their analysis
    result = await db.execute(
        select(Document, DocAnalysis).outerjoin(
            DocAnalysis, Document.id == DocAnalysis.document_id
        ).where(
            Document.project_id.in_(project_ids),
            Document.ingestion_completed == True
        )
    )
    
    doc_analyses = result.all()
    logger.info(f"Found {len(doc_analyses)} documents with analysis in projects {project_ids}")
    
    training_data = []
    skipped = 0
    
    for doc, analysis in doc_analyses:
        if not analysis:
            skipped += 1
            continue
        
        # Query chunks for this document
        chunks_result = await db.execute(
            select(Chunk).where(Chunk.document_id == doc.id).order_by(Chunk.chunk_index)
        )
        chunks = chunks_result.scalars().all()
        
        if not chunks:
            skipped += 1
            continue
        
        # Create training examples: chunk_text → analysis field
        for i, chunk in enumerate(chunks):
            if not chunk.text or len(chunk.text.strip()) < 20:
                continue
            
            # Parse JSON fields
            try:
                entities = json.loads(analysis.entities_json or "[]")
                topics = json.loads(analysis.topics_json or "[]")
                action_items = json.loads(analysis.action_items_json or "[]")
                decisions = json.loads(analysis.decisions_json or "[]")
            except (json.JSONDecodeError, TypeError):
                entities, topics, action_items, decisions = [], [], [], []
            
            # Build analysis summary for training
            analysis_output = {
                "executive_summary": analysis.executive_summary or "",
                "sentiment": analysis.sentiment or "Neutral",
                "entities": entities[:5],  # Limit to top 5
                "topics": topics[:5],
                "action_items": action_items[:3],
                "decisions": decisions[:2],
            }
            
            # Create training example
            training_item = {
                "instruction": (
                    f"Analyze the following document excerpt from '{doc.filename}' "
                    f"(chunk {i+1} of {len(chunks)}). Extract key entities, topics, "
                    "sentiment, action items, and decisions."
                ),
                "input": chunk.text[:1000],  # Limit input to avoid long contexts
                "output": json.dumps(analysis_output, ensure_ascii=False),
            }
            training_data.append(training_item)
    
    logger.info(f"Generated {len(training_data)} training examples (skipped {skipped} incomplete docs)")
    
    # Write JSONL file
    timestamp = __import__("datetime").datetime.now().strftime("%Y%m%d_%H%M%S")
    batch_filename = f"training_batch_{timestamp}.jsonl"
    batch_path = output_path / batch_filename
    
    with open(batch_path, "w", encoding="utf-8") as f:
        for item in training_data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    
    logger.info(f"Training batch exported to: {batch_path}")
    return str(batch_path)


async def export_document_chunks(
    document_id: int,
    output_dir: Optional[str] = None,
    db: Optional[AsyncSession] = None,
) -> str:
    """
    Export a single document's chunks without analysis (for preview/debugging).
    
    Args:
        document_id: Document ID to export
        output_dir: Directory to save
        db: AsyncSession
    
    Returns:
        Path to generated JSONL file
    """
    if db is None:
        from app.db.database import AsyncSessionLocal
        db = AsyncSessionLocal()
    
    if output_dir is None:
        output_dir = str(Path(settings.base_dir) / "training" / "batches")
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    result = await db.execute(
        select(Document).where(Document.id == document_id)
    )
    doc = result.scalar_one_or_none()
    
    if not doc:
        raise ValueError(f"Document {document_id} not found")
    
    chunks_result = await db.execute(
        select(Chunk).where(Chunk.document_id == document_id).order_by(Chunk.chunk_index)
    )
    chunks = chunks_result.scalars().all()
    
    training_data = []
    for i, chunk in enumerate(chunks):
        if not chunk.text or len(chunk.text.strip()) < 20:
            continue
        
        training_item = {
            "instruction": f"Here is a document chunk from '{doc.filename}':",
            "input": "",
            "output": chunk.text[:2000],
        }
        training_data.append(training_item)
    
    timestamp = __import__("datetime").datetime.now().strftime("%Y%m%d_%H%M%S")
    batch_filename = f"doc_{document_id}_{timestamp}.jsonl"
    batch_path = output_path / batch_filename
    
    with open(batch_path, "w", encoding="utf-8") as f:
        for item in training_data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    
    logger.info(f"Document chunks exported to: {batch_path}")
    return str(batch_path)
