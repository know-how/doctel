import asyncio
import logging
import mimetypes
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

from sqlalchemy import select

from app.config import settings
from app.db.database import AsyncSessionLocal
from app.db.models import Document, Project, User, Chunk, DocAnalysis, SuggestedPrompt
from app.services.ingestion_service import get_file_hash
from app.services.ingest_worker import enqueue
from app.utils.chroma_client import chroma

logger = logging.getLogger(__name__)


@dataclass
class BootstrapStatus:
    running: bool = False
    started_at: float = 0.0
    finished_at: float = 0.0
    scanned: int = 0
    new: int = 0
    updated: int = 0
    skipped: int = 0
    last_error: str = ""

    @property
    def percent(self) -> int:
        total = max(1, self.scanned)
        done = self.new + self.updated + self.skipped
        return int(min(100, (done / total) * 100))


_status = BootstrapStatus()
_lock = asyncio.Lock()
_watcher_task: Optional[asyncio.Task] = None


def get_bootstrap_status() -> dict:
    d = asdict(_status)
    d["percent"] = _status.percent
    return d


def _scan_paths() -> list[Path]:
    configured = [p for p in (settings.bootstrap.scan_paths or []) if str(p).strip()]
    if not configured:
        configured = [
            str(Path(settings.base_dir) / "data" / "projects"),
            str(Path(settings.base_dir) / "data" / "uploads"),
        ]
    return [Path(p) for p in configured]


def _iter_files(paths: list[Path]) -> list[Path]:
    exts = {".pdf", ".docx", ".txt", ".md", ".png", ".jpg", ".jpeg"}
    files: list[Path] = []
    for root in paths:
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            if p.suffix.lower() not in exts:
                continue
            files.append(p)
    return files


def _infer_project_name(p: Path) -> tuple[str, float, bool]:
    s = str(p).replace("\\", "/").lower()
    if "/data/projects/" in s:
        parts = s.split("/data/projects/", 1)[1].split("/")
        name = parts[0].strip()
        if name:
            return name, 0.9, False
    return "Uploads", 0.5, True


async def _ensure_project(db, name: str) -> Project:
    res = await db.execute(select(Project).where(Project.name == name))
    proj = res.scalar_one_or_none()
    if proj:
        return proj
    ares = await db.execute(select(User).where(User.username == "admin"))
    admin = ares.scalar_one_or_none()
    if not admin:
        admin = User(username="admin", role="admin")
        db.add(admin)
        await db.commit()
    proj = Project(name=name, owner_user_id=admin.id)
    db.add(proj)
    await db.commit()
    return proj


async def _reset_document_artifacts(db, doc: Document) -> None:
    try:
        await db.execute(select(Chunk).where(Chunk.document_id == doc.id))
    except Exception:
        pass
    cres = await db.execute(select(Chunk).where(Chunk.document_id == doc.id))
    chunks = list(cres.scalars().all())
    for ch in chunks:
        await db.delete(ch)
    ares = await db.execute(select(DocAnalysis).where(DocAnalysis.document_id == doc.id))
    analysis = ares.scalar_one_or_none()
    if analysis:
        await db.delete(analysis)
    pres = await db.execute(select(SuggestedPrompt).where(SuggestedPrompt.document_id == doc.id))
    prompts = list(pres.scalars().all())
    for p in prompts:
        await db.delete(p)
    await db.commit()
    try:
        chroma.delete_where(str(doc.project_id), {"document_id": doc.id})
    except Exception:
        pass


async def run_bootstrap_scan() -> None:
    async with _lock:
        _status.running = True
        _status.started_at = time.time()
        _status.finished_at = 0.0
        _status.scanned = 0
        _status.new = 0
        _status.updated = 0
        _status.skipped = 0
        _status.last_error = ""

    paths = _scan_paths()
    files = _iter_files(paths)
    async with _lock:
        _status.scanned = len(files)

    start = time.time()
    try:
        async with AsyncSessionLocal() as db:
            ares = await db.execute(select(User).where(User.username == "admin"))
            admin = ares.scalar_one_or_none()
            if not admin:
                admin = User(username="admin", role="admin")
                db.add(admin)
                await db.commit()
            for fp in files:
                try:
                    sha = await get_file_hash(str(fp))
                    res = await db.execute(select(Document).where(Document.path == str(fp)))
                    doc = res.scalar_one_or_none()

                    project_name, conf, needs_review = _infer_project_name(fp)
                    project = await _ensure_project(db, project_name)
                    mime = mimetypes.guess_type(str(fp))[0] or "application/octet-stream"

                    if not doc:
                        doc = Document(
                            project_id=project.id,
                            uploaded_by_user_id=admin.id,
                            filename=fp.name,
                            path=str(fp),
                            mime_type=mime,
                            sha256=sha,
                            pages=0,
                            doc_type=fp.suffix.lower().lstrip("."),
                            doc_date="",
                            status="uploaded",
                            ingest_step="uploaded",
                            ingest_percent=0,
                            ingest_message="Queued for ingestion",
                            error_message="",
                            detected_type="",
                            auto_project_confidence=conf,
                            needs_project_review=needs_review,
                        )
                        db.add(doc)
                        await db.commit()
                        async with _lock:
                            _status.new += 1
                        await enqueue(int(doc.id))
                        continue

                    ares = await db.execute(select(DocAnalysis.id).where(DocAnalysis.document_id == doc.id))
                    has_analysis = bool(ares.first())

                    if has_analysis and not settings.bootstrap.overwrite_existing_analysis:
                        doc.project_id = project.id
                        doc.sha256 = sha
                        doc.mime_type = mime
                        doc.filename = fp.name
                        doc.status = "completed"
                        doc.ingest_step = "done"
                        doc.ingest_percent = 100
                        doc.ingest_message = "Completed"
                        doc.error_message = ""
                        doc.analysis_ready = True
                        doc.ingestion_started = True
                        doc.ingestion_completed = True
                        doc.ingestion_failed = False
                        db.add(doc)
                        await db.commit()
                        async with _lock:
                            _status.skipped += 1
                        continue

                    if doc.sha256 == sha and doc.status == "completed" and not settings.bootstrap.overwrite_existing_analysis:
                        ares = await db.execute(select(DocAnalysis.id).where(DocAnalysis.document_id == doc.id))
                        if ares.first():
                            doc.status = "completed"
                            doc.ingest_step = "done"
                            doc.ingest_percent = 100
                            doc.ingest_message = "Completed"
                            doc.error_message = ""
                            doc.analysis_ready = True
                            doc.ingestion_started = True
                            doc.ingestion_completed = True
                            doc.ingestion_failed = False
                            db.add(doc)
                            await db.commit()
                        async with _lock:
                            _status.skipped += 1
                        continue

                    doc.project_id = project.id
                    doc.sha256 = sha
                    doc.mime_type = mime
                    doc.filename = fp.name
                    if getattr(doc, "uploaded_by_user_id", None) is None:
                        doc.uploaded_by_user_id = admin.id
                    doc.auto_project_confidence = conf
                    doc.needs_project_review = needs_review
                    db.add(doc)
                    await db.commit()
                    await _reset_document_artifacts(db, doc)
                    async with _lock:
                        _status.updated += 1
                    await enqueue(int(doc.id))
                except Exception as e:
                    async with _lock:
                        _status.last_error = str(e)
    finally:
        async with _lock:
            _status.running = False
            _status.finished_at = time.time()
        elapsed = int(time.time() - start)
        logger.info(
            "DocTel Bootstrap | Scanned=%s New=%s Updated=%s Skipped=%s | Elapsed=%02d:%02d",
            _status.scanned,
            _status.new,
            _status.updated,
            _status.skipped,
            elapsed // 60,
            elapsed % 60,
        )


async def start_watcher() -> None:
    global _watcher_task
    if _watcher_task and not _watcher_task.done():
        return

    async def loop():
        while True:
            await asyncio.sleep(max(30, int(settings.bootstrap.schedule_seconds or 90)))
            try:
                await run_bootstrap_scan()
            except Exception:
                try:
                    logger.exception("bootstrap watcher scan failed")
                except Exception:
                    pass

    _watcher_task = asyncio.create_task(loop())
