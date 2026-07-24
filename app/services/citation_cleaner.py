"""
Post-generation citation & metadata formatter.

Cleans AI response text before it reaches the user:
- Strips inline "Based on the provided context" AI-isms
- Removes inline "Chunk N" / "(Source: ..., Chunk N)" references
- Replaces raw filenames with human-readable titles
- Removes internal document_id / chunk_index leaks
- Collapses internal metadata that should only appear in citation cards
"""

import re
import logging

logger = logging.getLogger(__name__)

# ── Patterns that indicate internal RAG mechanics leaked into the answer ─────

# "Based on the provided context" / "Based on the context" / "Based on the document"
_AI_ISM_PATTERNS = [
    re.compile(
        r"\bBased\s+on\s+(the\s+)?(provided\s+)?(context|document|text|information|source)s?\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bAccording\s+to\s+(the\s+)?(provided\s+)?(context|document|text|information|source)s?\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bThe\s+(provided\s+)?(context|document|text|information|source)\s+(indicates|states|mentions|says|shows|suggests|contains|provides)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bFrom\s+(the\s+)?(provided\s+)?(context|document|text|information)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bUsing\s+(the\s+)?(provided\s+)?(context|document|text|information)\b",
        re.IGNORECASE,
    ),
]

# Inline "Chunk N" or "(Source: filename, Chunk N)" patterns
_INLINE_CHUNK_PATTERNS = [
    # (Source: filename, Chunk N) — with optional comma
    re.compile(
        r"\(Source:\s*[^)]+,\s*Chunk\s+\d+\s*\)",
        re.IGNORECASE,
    ),
    # [Source: filename, Chunk N]
    re.compile(
        r"\[Source:\s*[^\]]+,\s*Chunk\s+\d+\s*\]",
        re.IGNORECASE,
    ),
    # standalone "Chunk N" or "chunk N" (but not "chunk" as in a piece)
    re.compile(
        r"\b[Cc]hunk\s+\d+\b",
    ),
    # "📖 SOURCE: filename (Chunk N)" — legacy format
    re.compile(
        r"📖\s*SOURCE:\s*[^\n]*\(Chunk\s+\d+\)",
        re.IGNORECASE,
    ),
    # "Source: filename, Chunk N" (no parens)
    re.compile(
        r"\bSource:\s*[^,\n]+,\s*Chunk\s+\d+\b",
        re.IGNORECASE,
    ),
    # "Source: filename.pdf" (without Chunk N) — the LLM often adds just the filename
    re.compile(
        r"\bSource:\s*[^\n]+?\.(?:pdf|docx?|doc|txt|xlsx?|ppt|pptx)\b",
        re.IGNORECASE,
    ),
    # Standalone "Source: Document Name" on a line by itself
    # The system prompt instructs the LLM to place source attributions on their own line:
    # "Format as: 'Source: Document Name'. One source per line."
    re.compile(
        r"^Source:\s*[^\n]+$",
        re.MULTILINE | re.IGNORECASE,
    ),
    # (Chunk N) with parens
    re.compile(
        r"\([Cc]hunk\s+\d+\)",
    ),
    # 📄 filename prefix
    re.compile(
        r"📄\s*[^\n]{2,60}\s*",
    ),
]

# Internal metadata formatting patterns
_INTERNAL_META_PATTERNS = [
    re.compile(
        r"\bdocument_id[:=]\s*['\"]?[a-f0-9-]+['\"]?",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bchunk_index[:=]\s*\d+",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bproject_id[:=]\s*\d+",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bdistance[:=]\s*0\.\d+",
        re.IGNORECASE,
    ),
    re.compile(
        r"\brelevance[:=]\s*0\.\d+",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bscore[:=]\s*0\.\d+",
        re.IGNORECASE,
    ),
]

# File extensions to strip when they appear mid-sentence (not at end of citation line)
_FILE_EXT_PATTERN = re.compile(
    r"\b\w+\.(pdf|docx?|doc|txt|xlsx?|ppt|pptx|csv|json|yaml|yml|md|html?|xml)\b",
    re.IGNORECASE,
)


def _strip_ai_isms(text: str) -> str:
    """Remove 'Based on the provided context' and similar AI-isms."""
    for pattern in _AI_ISM_PATTERNS:
        text = pattern.sub("", text)
    return text


def _strip_inline_chunks(text: str) -> str:
    """Remove inline 'Chunk N', '(Source: ..., Chunk N)' etc."""
    for pattern in _INLINE_CHUNK_PATTERNS:
        text = pattern.sub("", text)
    return text


def _strip_internal_meta(text: str) -> str:
    """Remove raw metadata keys leaked into the answer body."""
    for pattern in _INTERNAL_META_PATTERNS:
        text = pattern.sub("", text)
    return text


def _clean_file_extensions(text: str) -> str:
    """Remove file extensions like .pdf, .docx from inline text.

    Only strips when the extension appears mid-sentence (followed by more text),
    not at the end of a sentence or citation card text.
    """
    return _FILE_EXT_PATTERN.sub(
        lambda m: m.group(0).rsplit(".", 1)[0],
        text,
    )


def _clean_whitespace(text: str) -> str:
    """Collapse repeated whitespace left after removals."""
    # Remove empty parentheticals and brackets
    text = re.sub(r"\(\s*\)", "", text)
    text = re.sub(r"\[\s*\]", "", text)
    # Remove double-commas
    text = re.sub(r",\s*,", ",", text)
    # Remove space before comma/period/semicolon left after chunk removal
    text = re.sub(r"\s+([,.;])", r"\1", text)
    # Collapse multiple spaces
    text = re.sub(r"\s{2,}", " ", text)
    # Clean up leading/trailing punctuation and whitespace
    text = re.sub(r"^\s*[,.;:\s]+", "", text)
    text = re.sub(r"[,.;\s]+\s*$", "", text)
    # Ensure single space after periods (avoid "word.Word")
    text = re.sub(r"\.(\w)", ". \\1", text)
    return text.strip()


def _humanize_filename(text: str) -> str:
    """Replace raw filenames (with extension) with cleaner names inline.

    Only targets patterns where the filename appears as a standalone reference
    within flowing text — not inside citation cards.
    """
    # Match patterns like "ZETDC_DocTel_LLM_FRS_2026.pdf" in text
    # and replace with "DocTel LLM FRS 2026"
    def _replace_name(match: re.Match) -> str:
        raw = match.group(0)
        # Strip extension
        name = re.sub(r"\.(pdf|docx?|doc|txt|xlsx?|ppt|pptx|csv|json|yaml|yml|md|html?|xml)$", "", raw, flags=re.IGNORECASE)
        # Remove noisy prefixes
        name = re.sub(r"^(ZETDC_|DocTel_|draft_|v\d+_)", "", name, flags=re.IGNORECASE)
        # Replace separators with spaces
        name = name.replace("_", " ").replace("-", " ")
        # Collapse multiple spaces
        name = re.sub(r"\s+", " ", name).strip()
        return name if name else raw

    # Match a word containing underscores or known prefixes followed by a file extension
    return re.sub(
        r"\b(?:\w+_+\w+\.(?:pdf|docx?|doc|txt|xlsx?|ppt|pptx|csv|json|yaml|yml|md|html?|xml))\b",
        _replace_name,
        text,
        flags=re.IGNORECASE,
    )


def clean_response_text(text: str) -> str:
    """Main entry point: apply all cleaning passes to AI response text.

    Args:
        text: The raw AI-generated response text.

    Returns:
        Cleaned text suitable for user-facing display.
    """
    if not text:
        return text or ""

    original = text
    text = _strip_ai_isms(text)
    text = _strip_inline_chunks(text)
    text = _strip_internal_meta(text)
    text = _humanize_filename(text)
    text = _clean_file_extensions(text)
    text = _clean_whitespace(text)

    if text != original:
        logger.debug(
            "clean_response_text: cleaned %d chars → %d chars",
            len(original),
            len(text),
        )

    return text
