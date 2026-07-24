"""Audio transcription, metadata, and meeting analysis endpoints."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.routers.deps import (
    APIRouter,
    UploadFile,
    File,
    Form,
    Depends,
    HTTPException,
    JSONResponse,
    select,
    User,
    get_current_user,
    get_db,
    settings,
    uuid,
    AsyncSession,
    DbSession,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["audio"])


# ── GET /api/diagnostics/audio — audio pipeline health check ────────────


@router.get("/api/diagnostics/audio")
async def audio_diagnostics():
    """
    Diagnose the audio transcription pipeline.

    Reports the availability of each component in the transcription chain:
    - Gemini API key (primary transcription engine)
    - Local Whisper model (fallback transcription engine)
    - FFmpeg (audio extraction from video files)
    - Last transcription error (if any)

    Returns a JSON object with component-level status and an overall
    ``audio_processing_available`` boolean.
    """
    result: dict[str, any] = {}

    # ── 1. Gemini ─────────────────────────────────────────────────────
    try:
        from app.services.gemini_service import _api_key as _gemini_api_key
        from app.services.gemini_service import get_display_name
        key = _gemini_api_key()
        gemini_configured = bool(key)
        result["gemini"] = {
            "configured": gemini_configured,
            "display_name": get_display_name() if gemini_configured else None,
            "hint": "Add a Gemini API key via Admin > Providers or set GEMINI_API_KEY in your .env file."
            if not gemini_configured else None,
        }
    except Exception as e:
        result["gemini"] = {
            "configured": False,
            "error": str(e),
            "hint": "Gemini service module could not be loaded.",
        }
        gemini_configured = False

    # ── 2. Whisper (local) ─────────────────────────────────────────────
    whisper_available = False
    whisper_detail: dict[str, any] = {}
    try:
        import importlib.util as _imp_util
        whisper_detail["transformers"] = _imp_util.find_spec("transformers") is not None
        whisper_detail["torch"] = _imp_util.find_spec("torch") is not None
        whisper_detail["librosa"] = _imp_util.find_spec("librosa") is not None
        whisper_available = all(whisper_detail.values())
    except Exception as e:
        whisper_detail["error"] = str(e)
    result["whisper_local"] = {
        "available": whisper_available,
        "dependencies": whisper_detail,
        "hint": "Install with: pip install transformers torch librosa"
        if not whisper_available else None,
    }

    # ── 3. FFmpeg ──────────────────────────────────────────────────────
    ffmpeg_available = False
    try:
        from app.services.transcription_service import _has_ffmpeg
        ffmpeg_available = bool(_has_ffmpeg())
    except Exception:
        ffmpeg_available = False
    result["ffmpeg"] = {
        "available": ffmpeg_available,
        "hint": "Install ffmpeg (apt: sudo apt install ffmpeg, brew: brew install ffmpeg, choco: choco install ffmpeg)"
        if not ffmpeg_available else None,
    }

    # ── 4. Last transcription error ────────────────────────────────────
    try:
        from app.services.transcription_service import get_last_transcription_error
        last_error = get_last_transcription_error()
        result["last_transcription_error"] = last_error or None
    except Exception:
        result["last_transcription_error"] = None

    # ── 5. Overall processing availability ─────────────────────────────
    result["audio_processing_available"] = gemini_configured or whisper_available
    result["primary_method"] = "gemini" if gemini_configured else ("whisper_local" if whisper_available else None)
    result["fallback_method"] = "whisper_local" if (gemini_configured and whisper_available) else None

    return result


# ── Shared helpers ─────────────────────────────────────────────────────────

_AUDIO_MIME_MAP = {
    ".wav": "audio/wav",
    ".mp3": "audio/mpeg",
    ".mp4": "audio/mp4",
    ".m4a": "audio/mp4",
    ".ogg": "audio/ogg",
    ".webm": "audio/webm",
    ".flac": "audio/flac",
    ".aac": "audio/aac",
}


def _resolve_mime(filename: str, content_type: Optional[str] = None) -> str:
    ext = Path(filename or "").suffix.lower()
    return _AUDIO_MIME_MAP.get(ext, content_type or "audio/wav")


# ── POST /api/audio/transcribe — transcribe an audio file ─────────────────


@router.post("/api/audio/transcribe")
async def transcribe_audio(
    audio: UploadFile = File(...),
    language: str = Form("en"),
    user: User = Depends(get_current_user),
):
    from app.services.transcription_service import transcribe_file_structured

    temp_path = settings.uploads_dir / f"audio_{uuid.uuid4().hex}_{audio.filename}"
    try:
        content = await audio.read()
        with open(temp_path, "wb") as f:
            f.write(content)

        mime_type = _resolve_mime(audio.filename or "", audio.content_type)
        result = await transcribe_file_structured(str(temp_path), mime_type=mime_type)

        if not result.full_text:
            from app.services.transcription_service import diagnose_transcription_failure
            diagnosis = diagnose_transcription_failure()
            return JSONResponse(
                status_code=503,
                content={
                    "error": "audio_transcription_unavailable",
                    "message": diagnosis.get("message", "Audio transcription failed."),
                    "diagnosis": diagnosis,
                },
            )

        return {
            "text": result.full_text.strip(),
            "language": result.language or language,
            "model": result.model_used or "gemini/whisper-local",
            "duration_sec": result.duration_sec,
            "word_count": result.word_count,
            "segments": [
                {
                    "start_sec": s.start_sec,
                    "end_sec": s.end_sec,
                    "text": s.text,
                    "confidence": s.confidence,
                    "speaker": s.speaker,
                }
                for s in result.segments
            ],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Transcription failed: %s", e, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": "transcription_failed", "detail": str(e)},
        )
    finally:
        try:
            if temp_path.exists():
                temp_path.unlink()
        except Exception:
            pass


# ── GET /api/audio/metadata/{document_id} — retrieve audio metadata ────────


@router.get("/api/audio/metadata/{document_id}")
async def get_audio_metadata(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Retrieve audio-specific metadata for a document that has been
    ingested as audio or video."""
    from app.db.models import AudioMetadata, Document as DbDocument
    from app.routers.deps import _parse_document_id, _assert_document_workspace_access

    doc_id = _parse_document_id(document_id)
    from sqlalchemy import select as sa_select

    doc_result = await db.execute(sa_select(DbDocument).where(DbDocument.id == doc_id))
    doc = doc_result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    await _assert_document_workspace_access(doc, user, db)

    meta_result = await db.execute(
        sa_select(AudioMetadata).where(AudioMetadata.document_id == doc.id)
    )
    meta = meta_result.scalar_one_or_none()

    return {
        "document_id": str(doc.id),
        "filename": doc.filename,
        "title": doc.title,
        "detected_type": doc.detected_type,
        "status": doc.status,
        "has_transcript": bool(doc.ingestion_completed),
        "metadata": {
            "duration_sec": meta.duration_sec if meta else None,
            "language": meta.language if meta else None,
            "speaker_count": meta.speaker_count if meta else None,
            "speakers": json.loads(meta.speakers_json or "[]") if meta and meta.speakers_json else [],
            "transcription_model": meta.transcription_model if meta else None,
            "has_diarization": meta.has_diarization if meta else False,
            "processing_time_ms": meta.processing_time_ms if meta else None,
            "source_type": meta.source_type if meta else (doc.detected_type or "audio"),
            "word_count": meta.word_count if meta else None,
        } if meta else {},
    }


# ── POST /api/audio/metadata/{document_id} — store/update audio metadata ──


@router.post("/api/audio/metadata/{document_id}")
async def update_audio_metadata(
    document_id: str,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Store or update audio metadata for a document."""
    from app.db.models import AudioMetadata, Document as DbDocument
    from app.routers.deps import _parse_document_id, _assert_document_workspace_access
    from sqlalchemy import select as sa_select

    doc_id = _parse_document_id(document_id)
    doc_result = await db.execute(sa_select(DbDocument).where(DbDocument.id == doc_id))
    doc = doc_result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    await _assert_document_workspace_access(doc, user, db)

    # Upsert: find existing or create new
    meta_result = await db.execute(
        sa_select(AudioMetadata).where(AudioMetadata.document_id == doc.id)
    )
    meta = meta_result.scalar_one_or_none()
    if not meta:
        meta = AudioMetadata(document_id=doc.id)
        db.add(meta)

    if payload.get("duration_sec") is not None:
        meta.duration_sec = float(payload["duration_sec"])
    if payload.get("language"):
        meta.language = str(payload["language"])
    if payload.get("speaker_count") is not None:
        meta.speaker_count = int(payload["speaker_count"])
    if payload.get("speakers"):
        meta.speakers_json = json.dumps(payload["speakers"])
    if payload.get("transcription_model"):
        meta.transcription_model = str(payload["transcription_model"])
    if payload.get("has_diarization") is not None:
        meta.has_diarization = bool(payload["has_diarization"])
    if payload.get("processing_time_ms") is not None:
        meta.processing_time_ms = int(payload["processing_time_ms"])
    if payload.get("source_type"):
        meta.source_type = str(payload["source_type"])
    if payload.get("word_count") is not None:
        meta.word_count = int(payload["word_count"])

    await db.commit()
    return {"ok": True}


# ── POST /api/meeting/analyze — analyze a meeting transcript ────────────────


@router.post("/api/meeting/analyze")
async def analyze_meeting(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Analyze a meeting transcript and return structured meeting output.

    Expects:
        transcript (str): The full meeting transcript text.
        title (str, optional): Meeting title hint.
        duration_minutes (float, optional): Meeting duration.

    Returns:
        Structured MeetingResult with summary, agenda, decisions, actions, etc.
    """
    transcript = (payload.get("transcript") or "").strip()
    if not transcript:
        raise HTTPException(status_code=400, detail="Missing transcript")

    title_hint = (payload.get("title") or "").strip() or None
    duration_minutes = payload.get("duration_minutes")

    if duration_minutes is not None:
        try:
            duration_minutes = float(duration_minutes)
        except (ValueError, TypeError):
            duration_minutes = None

    from app.services.meeting_analysis_service import analyze_meeting_transcript, meeting_result_to_dict

    result = await analyze_meeting_transcript(
        transcript_text=transcript,
        db=db,
        title_hint=title_hint,
        duration_minutes=duration_minutes,
    )

    return meeting_result_to_dict(result)


# ── POST /api/audio/attach-to-session — attach transcript to a chat session ─


@router.post("/api/audio/attach-to-session")
async def attach_audio_to_session(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Attach an audio transcript to an active chat session.

    Once attached, every subsequent question in the session automatically
    references the transcript as conversational context. No re-transcription
    is needed — the transcript remains available throughout the session.

    Expects:
        session_id (str): The session UUID to attach to.
        filename (str): Original audio filename.
        transcript (str): The full transcript text.
        summary (str, optional): Meeting summary or description.
        duration_sec (float, optional): Audio duration.
        entities (list[str], optional): Extracted entities.
        topics (list[str], optional): Extracted topics.
        speaker_count (int, optional): Number of speakers detected.

    Returns:
        The updated session state including audio context.
    """
    session_id = (payload.get("session_id") or "").strip()
    if not session_id:
        raise HTTPException(status_code=400, detail="Missing session_id")

    session_result = await db.execute(
        select(DbSession).where(DbSession.session_uuid == session_id)
    )
    s = session_result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    if s.user_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    from app.services.session_state_service import attach_audio_to_session as _attach

    new_state = await _attach(
        db,
        session_id,
        filename=(payload.get("filename") or "audio_recording.mp3").strip(),
        transcript=(payload.get("transcript") or "").strip(),
        summary=(payload.get("summary") or "").strip(),
        entities=payload.get("entities") or [],
        topics=payload.get("topics") or [],
        duration_sec=payload.get("duration_sec"),
        speaker_count=payload.get("speaker_count"),
    )
    return {
        "ok": True,
        "session_id": session_id,
        "audio_source": new_state.get("current_audio_source"),
        "transcript_length": len(new_state.get("current_transcript", "")),
        "state": new_state,
    }


# ── POST /api/audio/remove-from-session — detach audio from a chat session ─


@router.post("/api/audio/remove-from-session")
async def remove_audio_from_session(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Remove the attached audio recording from a session's context."""
    session_id = (payload.get("session_id") or "").strip()
    if not session_id:
        raise HTTPException(status_code=400, detail="Missing session_id")

    session_result = await db.execute(
        select(DbSession).where(DbSession.session_uuid == session_id)
    )
    s = session_result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    if s.user_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    from app.services.session_state_service import remove_audio_from_session as _remove
    new_state = await _remove(db, session_id)

    return {"ok": True, "session_id": session_id, "state": new_state}


# ── GET /api/meeting/summary/{document_id} — retrieve stored meeting summary ─


@router.get("/api/meeting/summary/{document_id}")
async def get_meeting_summary(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Retrieve previously computed meeting summary for a document.

    Meeting summaries are stored as DocAnalysis records with
    meeting-specific fields. If no meeting analysis exists yet,
    the endpoint returns a 404.
    """
    from app.db.models import DocAnalysis, Document as DbDocument
    from app.routers.deps import _parse_document_id, _assert_document_workspace_access
    from sqlalchemy import select as sa_select

    doc_id = _parse_document_id(document_id)
    doc_result = await db.execute(sa_select(DbDocument).where(DbDocument.id == doc_id))
    doc = doc_result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    await _assert_document_workspace_access(doc, user, db)

    analysis_result = await db.execute(
        sa_select(DocAnalysis).where(DocAnalysis.document_id == doc.id)
    )
    analysis = analysis_result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(
            status_code=404,
            detail="No meeting analysis found. Upload the audio file and ingest it first.",
        )

    def _safe_json(val):
        if not val:
            return []
        try:
            return json.loads(val) if isinstance(val, str) else (val or [])
        except (json.JSONDecodeError, TypeError):
            return []

    return {
        "document_id": str(doc.id),
        "filename": doc.filename,
        "title": doc.title,
        "executive_summary": analysis.executive_summary or "",
        "detailed_summary": analysis.detailed_summary or "",
        "sentiment": analysis.sentiment or "Neutral",
        "entities": _safe_json(analysis.entities_json),
        "topics": _safe_json(analysis.topics_json),
        "action_items": _safe_json(analysis.action_items_json),
        "decisions": _safe_json(analysis.decisions_json),
    }
