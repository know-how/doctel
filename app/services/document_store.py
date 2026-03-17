from typing import Dict, Any


_document_store: Dict[str, Dict[str, Any]] = {
    "doc_1": {
        "filename": "sample-document.pdf",
        "content_type": "application/pdf",
        "metadata": {
            "project_id": "proj_1",
            "project_name": "DocIntel Demo",
            "document_type": "Specification",
            "document_date": "2026-01-15",
        },
    }
}
_document_counter = 2
_project_store: Dict[str, Dict[str, Any]] = {
    "proj_1": {"name": "DocIntel Demo", "document_ids": ["doc_1"]}
}
_project_counter = 2


def create_document(
    filename: str,
    content_type: str,
    metadata: Dict[str, Any] | None,
    storage_path: str | None = None,
    document_id: str | None = None,
) -> str:
    global _document_counter
    if document_id is None:
        document_id = f"doc_{_document_counter}"
        _document_counter += 1
    _document_store[document_id] = {
        "filename": filename,
        "content_type": content_type,
        "metadata": metadata or {},
        "storage_path": storage_path,
    }
    return document_id


def create_project(name: str, project_id: str | None = None) -> str:
    global _project_counter
    if project_id is None:
        project_id = f"proj_{_project_counter}"
        _project_counter += 1
    _project_store[project_id] = {"name": name, "document_ids": []}
    return project_id


def list_projects() -> Dict[str, Dict[str, Any]]:
    return _project_store


def get_project(project_id: str) -> Dict[str, Any] | None:
    return _project_store.get(project_id)


def get_project_by_name(name: str) -> str | None:
    for project_id, project in _project_store.items():
        if project.get("name") == name:
            return project_id
    return None


def add_document_to_project(document_id: str, project_id: str) -> None:
    project = _project_store.get(project_id)
    if not project:
        return
    if document_id not in project["document_ids"]:
        project["document_ids"].append(document_id)


def list_project_documents(project_id: str) -> list[str]:
    project = _project_store.get(project_id)
    if not project:
        return []
    return list(project.get("document_ids", []))


def document_exists(document_id: str) -> bool:
    return document_id in _document_store


def get_document(document_id: str) -> Dict[str, Any] | None:
    return _document_store.get(document_id)


def get_document_metadata(document_id: str) -> Dict[str, Any] | None:
    entry = _document_store.get(document_id)
    if not entry:
        return None
    return entry.get("metadata")


def set_document_storage_path(document_id: str, storage_path: str) -> None:
    entry = _document_store.get(document_id)
    if not entry:
        return
    entry["storage_path"] = storage_path


def get_document_storage_path(document_id: str) -> str | None:
    entry = _document_store.get(document_id)
    if not entry:
        return None
    return entry.get("storage_path")

