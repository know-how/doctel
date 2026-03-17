from datetime import datetime
from typing import Dict, List, Any
from app.models import DocumentAnalysisResponse


_summary_history_store: Dict[str, List[Dict[str, Any]]] = {}


def append_summary_history(ec_number: str, analysis: DocumentAnalysisResponse) -> None:
    key = ec_number.strip()
    if not key:
        return
    entry = {
        "document_id": analysis.id,
        "executive_summary": analysis.executive_summary,
        "detailed_summary": analysis.detailed_summary,
        "topics": analysis.topics,
        "entities": analysis.entities,
        "key_entities": analysis.key_entities,
        "sentiment": analysis.sentiment,
        "action_items": analysis.action_items,
        "decisions": analysis.decisions,
        "created_at": datetime.utcnow().isoformat(),
    }
    _summary_history_store.setdefault(key, []).append(entry)


def get_summary_history(ec_number: str) -> List[Dict[str, Any]]:
    key = ec_number.strip()
    if not key:
        return []
    return list(_summary_history_store.get(key, []))
