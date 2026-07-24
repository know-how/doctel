"""
query_rewriter.py — Conversational query rewriting for RAG.

Detects follow-up questions that implicitly reference previous turns
and rewrites them into self-contained queries suitable for vector retrieval.

Examples:
  "What is OMS?"  →  "What is OMS?"
  "munei muzvikamu zvawataura"  →  "What modules/components of OMS were mentioned?"
  "tell me more"  →  "Tell me more about [previous topic]"
"""

from __future__ import annotations

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# ── Patterns that signal a follow-up question ──────────────────────────────
# These patterns indicate the current question refers to previous context
# and should be rewritten to include that context for retrieval.

_FOLLOW_UP_PATTERNS = [
    # Shona / Zimbabwean language follow-ups
    r"\bmunei\b",             # "what about"
    r"\bzvawataura\b",        # "you mentioned"
    r"\bzvawakataura\b",      # "what you said"
    r"\bzvandakataura\b",     # "what I said"
    r"\bchii\b",              # "what" (shona)
    r"\bndeipi\b",            # "which one"
    r"\bzvimwe\b",            # "more / other"
    r"\bwedzera\b",           # "add / elaborate"
    r"\btsanangura\b",        # "explain"
    # English follow-ups
    r"\btell me more\b",
    r"\belaborate\b",
    r"\bgo on\b",
    r"\bcontinue\b",
    r"\babout that\b",
    r"\bre:?\s*\w",
    r"\bexamples?\b",
    r"\bdetails?\b",
    r"\bmore\b",
    r"\bother\b",
    r"\bfurther\b",
    r"\badditional\b",
    r"\bexpand\b",
    r"\bwhat about\b",
    r"\bhow about\b",
    r"\bclarif\w+\b",
    r"\bspecific\w+\b",
    # Pronoun references — strongest signals of a follow-up
    r"\bits\b",            # "What is its relation to CRM?"
    r"\bit\b",              # "What does it do?"
    r"\bthey\b",            # "How do they differ?"
    r"\bthem\b",            # "What are their functions?"
    r"\bthis\b",            # "Explain this further"
    r"\bthese\b",           # "What are these modules?"
    r"\bthose\b",           # "How do those compare?"
    r"\bsuch\b",            # "What are such examples?"
    r"\bthe above\b",
    r"\baforementioned\b",
    r"\bpreviously\b",
    # Relationship / connection words
    r"\brelat\w*\b",        # relation, relationship, related
    r"\bconnect\w*\b",      # connection, connected
    r"\brefer\w*\b",        # referring, referred
    r"\bmention\w*\b",      # mentioned
    r"\bcompare\b",         # compare (covers 'comparison', 'comparing' via \b boundary)
    r"\bdifferen\w+\b",     # difference, different, differentiate
    r"\bversus\b",
    r"\bvs\.?\b",
]

# Very short questions (fewer than N chars) are almost always follow-ups
_SHORT_QUESTION_THRESHOLD = 15


def is_follow_up(question: str, history_length: int = 0) -> bool:
    """Return True if the question looks like a follow-up needing rewriting.

    Args:
        question: The user's current question.
        history_length: Number of existing messages in the conversation history.
                        When > 0, any question containing pronouns (its, it, they, this)
                        is treated as a follow-up.
    """
    q = question.strip().lower()
    if not q:
        return False
    # Very short questions are almost always follow-ups
    if len(q) < _SHORT_QUESTION_THRESHOLD:
        return True
    # Check for follow-up patterns
    for pattern in _FOLLOW_UP_PATTERNS:
        if re.search(pattern, q):
            return True
    # No question mark + short = likely follow-up
    if "?" not in q and len(q) < 40:
        return True
    # ── Pronoun heuristic: if history exists and question has pronouns, |
    # treat as follow-up even if no keyword match.
    # This catches: "What is its relation to CRM?", "How does it work?",
    # "What do they do?", "Is this linked to that?"
    if history_length > 0:
        # Check for common pronouns even if not captured by the pattern list
        pronoun_pattern = re.compile(
            r"\b(its|it|they|them|this|these|those|he|she|his|her|their)\b",
            re.IGNORECASE,
        )
        if pronoun_pattern.search(q):
            return True
    return False


def build_conversation_context(history: list[dict]) -> str:
    """Format recent conversation history into a compact context string.

    Args:
        history: List of {"role": "user"|"assistant", "content": str} dicts,
                 ordered oldest-first.

    Returns:
        A formatted string like:
          User: What is OMS?
          Assistant: OMS stands for Outage Management System...
    """
    if not history:
        return ""

    # Take the last 4 turns (user+assistant pairs = up to 8 messages)
    recent = history[-8:] if len(history) > 8 else history
    parts = []
    for msg in recent:
        role = msg.get("role", "user").capitalize()
        content = (msg.get("content", "") or "").strip()[:500]
        if content:
            parts.append(f"{role}: {content}")
    return "\n".join(parts)


def rewrite_question(
    question: str,
    history: list[dict],
    rewritten_questions: Optional[list[str]] = None,
) -> dict:
    """Rewrite a follow-up question to include conversational context.

    For standalone questions (first turn, or clearly self-contained),
    returns a dict with the original question unchanged.

    For follow-up questions, resolves pronouns/ellipsis by incorporating
    context from the conversation history into a standalone retrieval
    question suitable for embedding.

    Args:
        question: The user's current question.
        history: List of {"role": "user"|"assistant", "content": str} dicts.
        rewritten_questions: Optional list of previously rewritten questions
                             to avoid re-rewriting the same question.

    Returns:
        A dict with:
          - retrieval_question (str): Clean, self-contained query for embedding.
          - conversation_context (str): Formatted conversation history for LLM.
          - resolved_entities (list[str]): Entities resolved from context.
    """
    # Prevent re-rewriting — if this exact question was already rewritten, skip
    if rewritten_questions and question in rewritten_questions:
        return {
            "retrieval_question": question,
            "conversation_context": build_conversation_context(history),
            "resolved_entities": [],
        }

    # Build conversation context regardless
    conv_context = build_conversation_context(history)

    # If no history or this is the first turn, return as-is
    if not history:
        return {
            "retrieval_question": question,
            "conversation_context": "",
            "resolved_entities": [],
        }

    # Check if this is a follow-up
    if not is_follow_up(question):
        return {
            "retrieval_question": question,
            "conversation_context": conv_context,
            "resolved_entities": [],
        }

    # Extract the last assistant answer and user question from history
    last_answer = ""
    last_user_question = ""
    for msg in reversed(history):
        if msg.get("role") == "assistant" and not last_answer:
            last_answer = (msg.get("content", "") or "").strip()
        elif msg.get("role") == "user" and not last_user_question:
            last_user_question = (msg.get("content", "") or "").strip()
        if last_answer and last_user_question:
            break

    # ── Build a clean SELF-CONTAINED retrieval question ────────────────
    # The goal is to produce a standalone query like:
    #   "What is the relationship between OMS and CRM?"
    # instead of a composite string like:
    #   "Previous question: ... | Previous answer context: ... | Current question: ..."

    # Extract key entities from previous turns for pronoun resolution
    resolved_entities: list[str] = _extract_entities(last_user_question, last_answer)

    # Build the retrieval question by resolving references
    retrieval_question = _resolve_references(question, last_user_question, last_answer, resolved_entities)

    logger.info(
        "[QUERY_REWRITE] original=%r | retrieval_question=%r | entities=%s",
        question[:80], retrieval_question[:200], resolved_entities,
    )

    return {
        "retrieval_question": retrieval_question or question,
        "conversation_context": conv_context,
        "resolved_entities": resolved_entities,
    }


# ── Entity extraction helpers ─────────────────────────────────────────────


# Acronym pattern: 2–8 uppercase letters, optionally with trailing digits
_ACRONYM_RE = re.compile(r"\b[A-Z]{2,8}\d?\b")


def _extract_entities(user_question: str, assistant_answer: str) -> list[str]:
    """Extract key entities (acronyms, proper nouns) from context.

    Args:
        user_question: The previous user question.
        assistant_answer: The previous assistant answer.

    Returns:
        A list of unique entity strings, preserving order of first appearance.
    """
    seen: set[str] = set()
    entities: list[str] = []
    source_text = f"{user_question} {assistant_answer}"

    for match in _ACRONYM_RE.finditer(source_text):
        token = match.group()
        if token not in seen:
            seen.add(token)
            entities.append(token)

    return entities


def _resolve_references(
    question: str,
    last_user_question: str,
    last_answer: str,
    entities: list[str],
) -> str:
    """Resolve pronouns/ellipsis into a standalone retrieval question.

    Strategy (applied in order):
      1. If the question contains pronouns (its, it, they, them, this, these)
         and we have entities, replace the pronoun with the most relevant entity.
      2. If the question is very short (e.g. "tell me more"), prepend the
         topic from the previous user question.
      3. If the question asks for a relationship ("relation to CRM"), prepend
         the previous topic.
      4. Otherwise, create a combined question by prepending the topic context.

    Args:
        question: The current (follow-up) question.
        last_user_question: The previous user question.
        last_answer: The previous assistant answer (first 200 chars).
        entities: Resolved entities from context.

    Returns:
        A self-contained retrieval question string.
    """
    q = question.strip()
    prev_topic = last_user_question[:200] if last_user_question else ""
    answer_preview = last_answer[:150] if last_answer else ""

    # ── CASE 1: Pronoun resolution with known entities ────────────────
    if entities:
        pronoun_pattern = re.compile(
            r"\b(its|it|they|them|this|these|those)\b", re.IGNORECASE
        )
        if pronoun_pattern.search(q):
            # Replace pronoun with the primary entity (first one found)
            primary_entity = entities[0]
            resolved = pronoun_pattern.sub(primary_entity, q)
            # Ensure first letter case is correct
            if resolved and resolved[0].islower():
                resolved = resolved[0].upper() + resolved[1:]
            return resolved

    # ── CASE 2: Very short / generic follow-ups ───────────────────────
    # "tell me more", "elaborate", "examples?", "go on", etc.
    generic_pattern = re.compile(
        r"^(tell me more|elaborate|go on|continue|examples?\??|details?\??|"
        r"expand|clarif\w+|more|other|further|additional|wedzera|tsanangura|"
        r"zvimwe|munei)\b.*$",
        re.IGNORECASE,
    )
    if generic_pattern.match(q):
        if prev_topic:
            # Build a question like "Tell me more about [topic]"
            topic_clean = prev_topic.rstrip(".?!")
            return f"Tell me more about {topic_clean}"
        return q

    # ── CASE 3: Relationship / connection questions ───────────────────
    # "What is its relation to CRM?", "How does it connect with X?"
    relation_pattern = re.compile(
        r"\b(relation|relationship|connect|connection|link|compare|difference|"
        r"versus|vs\.?)\b", re.IGNORECASE,
    )
    if relation_pattern.search(q) and prev_topic:
        # Replace pronouns in relationship questions
        q_clean = re.sub(
            r"\b(its|it|they|them|this|these|those|the above|aforementioned)\b",
            lambda m: entities[0] if entities else "the topic",
            q,
            flags=re.IGNORECASE,
        )
        # If the result still feels generic, prepend context
        if len(q_clean.split()) <= 8 and not any(
            e in q_clean for e in entities
        ):
            topic_clean = prev_topic.rstrip(".?!")
            return f"Regarding {topic_clean}, {q_clean[0].lower()}{q_clean[1:]}"
        return q_clean

    # ── CASE 4: Generic context prepending ────────────────────────────
    # Question refers to previous context but doesn't match above patterns.
    # Create a combined query: embed the topic context naturally.
    if prev_topic:
        topic_phrase = _compact_topic(prev_topic)
        # Remove leading question words from topic
        topic_clean = re.sub(
            r"^(what|who|how|when|where|why|tell me about|explain)\s+",
            "", topic_phrase, flags=re.IGNORECASE,
        ).strip().rstrip("?")
        if topic_clean:
            return f"{q} — regarding {topic_clean}"

    return q


def _compact_topic(question: str, max_words: int = 12) -> str:
    """Compact a verbose question into a short topic phrase.

    E.g. "What are the key features of the Outage Management System?"
    → "Outage Management System"
    """
    # Remove leading question words
    compact = re.sub(
        r"^(what|who|how|when|where|why|tell me about|explain|describe)\s+"
        r"(are|is|do|does|can|could|would|will|shall|did|has|have|was|were)?\s*",
        "", question, flags=re.IGNORECASE,
    ).strip().rstrip("?")
    # Limit to max_words
    words = compact.split()
    if len(words) > max_words:
        words = words[:max_words]
    return " ".join(words).strip()
