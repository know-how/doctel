"""
Lightweight session-state tracker.

Maintains a JSON blob on the ``sessions`` row that records:
- ``entities_seen`` — entities/terms that have been discussed so far
- ``topic_history`` — ordered list of topic labels inferred from user questions
- ``last_turn_summary`` — a 1–2 sentence summary of the last user↔assistant
  exchange (useful when the raw message history is long)
- ``last_retrieval_question`` — the (possibly rewritten) query that retrieved
  chunks on the last turn, used to detect topic shifts

Usage
-----
After every successful RAG turn::

    from app.services.session_state_service import update_session_state
    await update_session_state(db, session_uuid, question, answer, entities)

Before the next RAG turn (in ask.py)::

    from app.services.session_state_service import get_session_state
    state = await get_session_state(db, session_uuid)
    if state:
        last_topic = state.get("topic_history", [])[-1:]  # most recent topic
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Session as DbSession

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_STOP_SUBJECTS = {
    "what", "who", "which", "how", "why", "when", "where",
    "is", "are", "was", "were", "do", "does", "did",
    "can", "could", "will", "would", "shall", "should",
    "has", "have", "had", "define", "describe", "explain",
    "list", "tell", "give", "name", "show",
}


def build_audio_context_string(state: Optional[dict]) -> str:
    """Build a compact context string from attached audio recording.

    If *state* contains audio context (from ``attach_audio_to_session``),
    returns a formatted block like:

        [Audio Recording: meeting_2024.mp3]
        Transcript summary: ...
        Duration: 5m 30s

    Returns an empty string if no audio context is attached.
    """
    if not state:
        return ""
    source = state.get("current_audio_source")
    if not source:
        return ""

    lines: list[str] = []
    lines.append(f"[Audio Recording: {source}]")
    summary = (state.get("current_audio_summary") or "").strip()
    if summary:
        lines.append(f"Transcript summary: {summary}")
    transcript = (state.get("current_transcript") or "").strip()
    if transcript:
        # Include a compact preview (first 1500 chars) of the transcript
        preview = transcript[:1500]
        if len(transcript) > 1500:
            preview += "...[truncated]"
        lines.append(f"Transcript content:\n{preview}")
    duration = state.get("audio_duration_sec")
    if duration is not None:
        mins = int(duration // 60)
        secs = int(duration % 60)
        lines.append(f"Duration: {mins}m {secs}s")
    entities = state.get("audio_entities", [])
    if entities:
        lines.append(f"Key entities: {', '.join(entities[:10])}")

    return "\n".join(lines)


def _infer_topic(question: str) -> str:
    """Extract a short topic label from the user's question."""
    text = question.strip().rstrip("?").strip()
    # Try to grab the first few meaningful words after any stop words
    words = text.split()
    # Skip leading stop words to find the subject
    i = 0
    while i < len(words) and words[i].lower().strip(",.!?") in _STOP_SUBJECTS:
        i += 1
    if i < len(words):
        topic_words = words[i:i + 5]  # up to 5 content words
        label = " ".join(topic_words).strip(",.!?")
        if label:
            return label[:80]
    # Fallback to first 6 words
    label = " ".join(words[:6])
    return label[:80] if label else question[:80]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def get_session_state(
    db: AsyncSession,
    session_uuid: str,
) -> Optional[dict[str, Any]]:
    """Return the deserialized conversation_state for *session_uuid*.

    Returns ``None`` when the session doesn't exist or the state column is
    empty.
    """
    result = await db.execute(
        select(DbSession.conversation_state).where(
            DbSession.session_uuid == session_uuid
        )
    )
    raw = result.scalar_one_or_none()
    if not raw:
        return None
    try:
        return json.loads(raw) if isinstance(raw, str) else raw
    except (json.JSONDecodeError, TypeError) as exc:
        logger.warning(
            "[SESSION_STATE] Failed to decode state for %s: %s",
            session_uuid, exc,
        )
        return None


async def attach_audio_to_session(
    db: AsyncSession,
    session_uuid: str,
    *,
    filename: str,
    transcript: str,
    summary: str = "",
    entities: Optional[list[str]] = None,
    topics: Optional[list[str]] = None,
    duration_sec: Optional[float] = None,
    speaker_count: Optional[int] = None,
) -> dict[str, Any]:
    """Attach an audio recording's transcript and metadata to a session.

    After calling this, every question in the session will automatically
    include the transcript as context — no re-transcription needed.

    Returns the **new** state dict (already committed).
    """
    current = await get_session_state(db, session_uuid) or {}

    current["current_audio_source"] = filename
    current["current_transcript"] = transcript
    current["current_audio_summary"] = summary or ""
    current["audio_entities"] = entities or []
    current["audio_topics"] = topics or []
    current["audio_duration_sec"] = duration_sec
    current["audio_speaker_count"] = speaker_count
    current["audio_attached_at"] = __import__("time").time()

    raw_json = json.dumps(current, ensure_ascii=False)
    await db.execute(
        update(DbSession)
        .where(DbSession.session_uuid == session_uuid)
        .values(conversation_state=raw_json)
    )
    await db.commit()
    logger.info(
        "[SESSION_AUDIO] Attached audio '%s' to session %s (transcript=%d chars)",
        filename, session_uuid, len(transcript),
    )
    return current


async def remove_audio_from_session(
    db: AsyncSession,
    session_uuid: str,
) -> dict[str, Any]:
    """Remove the attached audio recording context from a session.

    Returns the **new** state dict (already committed).
    """
    current = await get_session_state(db, session_uuid) or {}

    for key in ("current_audio_source", "current_transcript", "current_audio_summary",
                "audio_entities", "audio_topics", "audio_duration_sec",
                "audio_speaker_count", "audio_attached_at"):
        current.pop(key, None)

    raw_json = json.dumps(current, ensure_ascii=False)
    await db.execute(
        update(DbSession)
        .where(DbSession.session_uuid == session_uuid)
        .values(conversation_state=raw_json)
    )
    await db.commit()
    logger.info("[SESSION_AUDIO] Removed audio from session %s", session_uuid)
    return current


async def update_session_state(
    db: AsyncSession,
    session_uuid: str,
    question: str,
    answer: str,
    entities: Optional[list[str]] = None,
    retrieval_question: Optional[str] = None,
) -> dict[str, Any]:
    """Load current state, merge the latest turn, and persist.

    Returns the **new** state dict (already committed).
    """
    current = await get_session_state(db, session_uuid) or {}

    # ── entities_seen ─────────────────────────────────────────────────
    seen: set = set(current.get("entities_seen", []))
    if entities:
        for e in entities:
            if e and isinstance(e, str):
                seen.add(e.strip())
    # Also try to extract noun-phrase-like terms from the question
    for word in question.split():
        clean = word.strip(",.!?;:")
        if clean and len(clean) > 2 and clean[0].isupper() and not clean[0].isdigit():
            seen.add(clean)
    current["entities_seen"] = sorted(seen)

    # ── topic_history ──────────────────────────────────────────────────
    topic = _infer_topic(question)
    topics: list = current.get("topic_history", [])
    if not topics or topics[-1] != topic:
        topics.append(topic)
    current["topic_history"] = topics[-20:]  # keep last 20 topics

    # ── turn_count ─────────────────────────────────────────────────────
    # Track total turns so ask.py can check summarize intervals
    turn_count: int = current.get("turn_count", 0) + 1
    current["turn_count"] = turn_count

    # ── last_turn_summary ──────────────────────────────────────────────
    # Keep a very condensed 1-sentence summary of the last exchange
    q_short = (question or "")[:150].replace("\n", " ")
    a_short = (answer or "")[:200].replace("\n", " ")
    current["last_turn_summary"] = (
        f"User asked: {q_short} | Assistant answered: {a_short}"
    )

    # ── last_retrieval_question ────────────────────────────────────────
    if retrieval_question:
        current["last_retrieval_question"] = retrieval_question

    # ── Persist ────────────────────────────────────────────────────────
    raw_json = json.dumps(current, ensure_ascii=False)
    await db.execute(
        update(DbSession)
        .where(DbSession.session_uuid == session_uuid)
        .values(conversation_state=raw_json)
    )
    await db.commit()
    logger.debug(
        "[SESSION_STATE] Updated %s — turn=%d, entities=%d, topics=%d",
        session_uuid,
        turn_count,
        len(seen),
        len(topics),
    )
    return current
