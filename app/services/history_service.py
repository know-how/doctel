from typing import Dict, List, Any


_history_store: Dict[str, List[Dict[str, Any]]] = {}


def append_chat_history(
    ec_number: str,
    document_id: str,
    question: str,
    answer: str,
) -> None:
    key = ec_number.strip()
    if not key:
        return
    entry = {
        "document_id": document_id,
        "question": question,
        "answer": answer,
    }
    _history_store.setdefault(key, []).append(entry)


def get_chat_history(ec_number: str) -> List[Dict[str, Any]]:
    key = ec_number.strip()
    if not key:
        return []
    return list(_history_store.get(key, []))

