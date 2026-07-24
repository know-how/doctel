"""
session_summarizer.py — Auto-generates compact conversation summaries.

Every *N* turns (default 5), this service reads the recent message history,
sends it to a lightweight Ollama model for compression, and stores the
result in the session's ``conversation_state`` JSON blob.

When the raw message count exceeds the hard cap (20), the summary replaces
the oldest messages, keeping only recent turns for the LLM prompt while
preserving the compressed context from earlier turns.

Design
------
1. ``generate_summary(db, session_uuid, messages)`` → str
   - Takes the last N turns (user + assistant messages)
   - Calls a lightweight Ollama model (e.g. llama3.2:3b or qwen3:4b)
   - Returns a 2-4 sentence compact summary

2. ``store_summary(db, session_uuid, summary)`` → None
   - Loads current session state from `conversation_state`
   - Appends to `conversation_summaries` list
   - Persists via `update_session_state()`

3. ``get_compressed_history(session_state, raw_messages)`` → list[dict]
   - If summaries exist AND raw_messages > 10, returns:
     [{"role": "system", "content": "Session summary: ..."}] + last 10 raw_messages
   - Otherwise returns raw_messages unchanged

4. ``should_summarize(turn_count, interval=5)`` → bool
   - True when turn_count > 0 and turn_count % interval == 0
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Session as DbSession
from app.utils.ollama_client import ollama

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Summarize every N turns
_SUMMARIZE_INTERVAL = 5

# Maximum raw messages to keep in prompt when summary exists
_MAX_RAW_WITH_SUMMARY = 10

# Ollama model to use for summarization (fast, small)
_SUMMARIZATION_MODEL = "qwen3:4b"  # Lightweight, runs well on local hardware

# ---------------------------------------------------------------------------
# Core summarization
# ---------------------------------------------------------------------------


async def generate_summary(
    db: AsyncSession,
    session_uuid: str,
    messages: list[dict],
    model: str = _SUMMARIZATION_MODEL,
) -> str:
    """Generate a compact 2-4 sentence summary of *messages*.

    Args:
        db: Database session (used for model resolution if needed).
        session_uuid: Session identifier for logging.
        messages: List of {"role": "user"|"assistant", "content": str} dicts,
                  should be the *segment* of messages to summarize (e.g. last 5 turns).
        model: Ollama model name to use for summarization.

    Returns:
        A concise summary string, or a fallback message if the model call fails.
    """
    if not messages:
        return ""

    # Build a compact representation of the segment
    segment_lines = []
    for msg in messages:
        role = msg.get("role", "user").capitalize()
        content = (msg.get("content", "") or "").strip()[:300]
        if content:
            segment_lines.append(f"{role}: {content}")

    segment_text = "\n".join(segment_lines)
    if not segment_text.strip():
        return ""

    # Build the summarization prompt
    summary_prompt = (
        "Summarize the following conversation segment in 2-4 concise sentences. "
        "Focus on: what was asked, what was answered, key entities discussed, "
        "and any decisions or action items. Use plain language.\n\n"
        f"{segment_text}\n\n"
        "Summary:"
    )

    try:
        summary = await ollama.generate(
            model=model,
            prompt=summary_prompt,
            system="You are a conversation summarizer. Produce only the summary, no commentary.",
        )
        cleaned = (summary or "").strip()
        if cleaned:
            logger.info(
                "[SESSION_SUMMARIZER] Generated summary for session=%s "
                "(segment=%d msgs, model=%s, len=%d chars)",
                session_uuid, len(messages), model, len(cleaned),
            )
            return cleaned
    except Exception as exc:
        logger.warning(
            "[SESSION_SUMMARIZER] Summary generation failed for session=%s: %s",
            session_uuid, exc,
        )

    # Fallback: manual concatenation
    return _fallback_summary(messages)


def _fallback_summary(messages: list[dict]) -> str:
    """Generate a simple extractive summary when the LLM call fails."""
    topics: list[str] = []
    entities: set[str] = set()

    for msg in messages:
        content = (msg.get("content", "") or "").strip()
        if not content:
            continue
        # Extract first meaningful line
        first_line = content.split("\n")[0][:100]
        if msg.get("role") == "user":
            topics.append(first_line)
        # Extract acronyms as entities
        import re
        for match in re.finditer(r"\b[A-Z]{2,8}\b", content):
            token = match.group()
            if token not in {"THE", "AND", "FOR", "ARE", "WAS", "NOT",
                              "BUT", "ALL", "CAN", "HAS", "ITS", "MAY",
                              "PER", "YOU", "OUR", "YOUR", "THIS", "THAT"}:
                entities.add(token)

    ent_str = f" Entities: {', '.join(sorted(entities))}." if entities else ""
    topic_str = topics[0] if topics else "See messages above."
    return (
        f"The user asked about {topic_str}. "
        f"The assistant answered based on retrieved documents.{ent_str}"
    )


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------


async def store_summary(
    db: AsyncSession,
    session_uuid: str,
    summary: str,
    turn_count: int,
) -> None:
    """Append *summary* to the session's conversation_summaries list.

    Args:
        db: Database session.
        session_uuid: Session identifier.
        summary: The summary string to store.
        turn_count: Current turn count (for metadata).
    """
    if not summary:
        return

    # Load current state from session
    from app.services.session_state_service import get_session_state
    state = await get_session_state(db, session_uuid) or {}

    # Initialize or append to summaries list
    summaries: list[dict] = state.get("conversation_summaries", [])
    summaries.append({
        "summary": summary,
        "turn": turn_count,
        "char_count": len(summary),
    })
    # Keep only the last 10 summaries (covers 50+ turns)
    state["conversation_summaries"] = summaries[-10:]

    # Persist back to session
    raw_json = json.dumps(state, ensure_ascii=False)
    await db.execute(
        update(DbSession)
        .where(DbSession.session_uuid == session_uuid)
        .values(conversation_state=raw_json)
    )
    await db.commit()

    logger.info(
        "[SESSION_SUMMARIZER] Stored summary at turn %d for session=%s "
        "(total summaries=%d, len=%d chars)",
        turn_count, session_uuid, len(summaries), len(summary),
    )


# ---------------------------------------------------------------------------
# History compression
# ---------------------------------------------------------------------------


def get_compressed_history(
    session_state: Optional[dict[str, Any]],
    raw_messages: list[dict],
    max_raw: int = _MAX_RAW_WITH_SUMMARY,
) -> list[dict]:
    """Return a compressed conversation history for the LLM prompt.

    When summaries exist AND raw messages exceed *max_raw*, returns:
        [system summary message] + last *max_raw* raw messages

    Otherwise returns raw messages unchanged.

    Args:
        session_state: The deserialized conversation_state from the session,
                       or None.
        raw_messages: List of {"role": ..., "content": ...} from the DB.
        max_raw: Maximum raw messages to keep when summary exists.

    Returns:
        A list of message dicts suitable for `build_conversation_context()`.
    """
    if not raw_messages:
        return []

    if not session_state:
        return raw_messages

    summaries: list[dict] = session_state.get("conversation_summaries", [])
    if not summaries:
        return raw_messages

    # Only use summary if we have more than max_raw messages
    if len(raw_messages) <= max_raw:
        return raw_messages

    # Combine all summaries into one condensed block
    combined = _combine_summaries(summaries)

    # Return: [system summary] + recent messages
    compressed: list[dict] = [
        {"role": "system", "content": f"Session summary:\n{combined}"},
    ]
    compressed.extend(raw_messages[-max_raw:])

    logger.info(
        "[SESSION_SUMMARIZER] Compressed %d raw msgs → summary + %d recent "
        "(saved %d msgs from context window)",
        len(raw_messages), max_raw,
        len(raw_messages) - max_raw - 1,
    )
    return compressed


def _combine_summaries(summaries: list[dict], max_chars: int = 2000) -> str:
    """Combine multiple summaries into a single compact block.

    If total exceeds *max_chars*, only the most recent summaries are kept.
    """
    parts = []
    total = 0
    for s in reversed(summaries):
        text = s.get("summary", "").strip()
        if not text:
            continue
        turn = s.get("turn", "?")
        entry = f"[Turn {turn}] {text}"
        if total + len(entry) > max_chars:
            break
        parts.insert(0, entry)
        total += len(entry)

    return "\n\n".join(parts) if parts else ""


# ---------------------------------------------------------------------------
# Trigger logic
# ---------------------------------------------------------------------------


def should_summarize(
    turn_count: int,
    interval: int = _SUMMARIZE_INTERVAL,
) -> bool:
    """Return True when it's time to generate a summary.

    Summarizes at: 5, 10, 15, 20, ... turns.
    Skips turn 0 (first question) since there's nothing to summarize yet.

    Args:
        turn_count: The current turn number (1-based).
        interval: Generate every N turns (default 5).

    Returns:
        True if a summary should be generated after this turn.
    """
    return turn_count > 0 and turn_count % interval == 0


# ---------------------------------------------------------------------------
# Convenience: generate + store in one call
# ---------------------------------------------------------------------------


async def summarize_and_store(
    db: AsyncSession,
    session_uuid: str,
    messages: list[dict],
    turn_count: int,
) -> str:
    """Generate a summary of *messages* and store it in session state.

    This is the primary entry point for use in ask.py after a response.

    Args:
        db: Database session.
        session_uuid: Session identifier.
        messages: The segment of messages to summarize (last N turns).
        turn_count: Current turn count (1-based).

    Returns:
        The generated summary string, or empty string on failure.
    """
    if not messages:
        return ""

    summary = await generate_summary(db, session_uuid, messages)
    if summary:
        await store_summary(db, session_uuid, summary, turn_count)

    return summary or ""
