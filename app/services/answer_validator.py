"""
answer_validator.py — Answer grounding validation for RAG.

Extracts key claims from the model-generated answer and checks whether
each claim is supported by at least one retrieved chunk.  If the
grounding score falls below the threshold, the answer is replaced with
a neutral "insufficient evidence" message to prevent hallucination drift.

Design
------
1. ``_extract_claims(text)`` → list of normalized claim strings
   - Numbers / dates / percentages  (e.g. "47", "2024", "5%")
   - Acronyms and uppercase entities  (e.g. "OMS", "CRM", "NDPM")
   - Function / requirement IDs  (e.g. "F-CRM-007", "F-FWA-001")
   - Quoted phrases  (e.g. '"All Messages"')
   - Capitalised multi-word phrases (potential named entities)

2. ``_check_claim_in_chunks(claim, chunks)`` → bool
   - Each chunk is lowercased and checked for substring presence.
   - Numbers are compared as exact tokens (to avoid "47" matching "470").

3. ``validate_grounding(answer_text, chunks)`` → dict
   - Combines extraction + checking.
   - Returns score = grounded_claims / total_claims.
   - Flags ungrounded claims for logging.

4. Threshold: >= 30 % of claims must be grounded.  Below that → replace answer.
   - If total_claims <= 2 → accept (too few to judge reliably).
   - If answer is very short (< 50 chars) → accept (greetings / confirmations).
"""

from __future__ import annotations

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

# Minimum fraction of claims that must be grounded (0.0 – 1.0)
_GROUNDING_THRESHOLD = 0.30

# Answers shorter than this (chars) skip validation entirely
_MIN_ANSWER_LENGTH = 50

# If total claims extracted is below this number, accept (too few to judge)
_MIN_CLAIMS_FOR_REJECTION = 3

# ---------------------------------------------------------------------------
# Claim extraction
# ---------------------------------------------------------------------------

# Pattern for function / requirement IDs like F-CRM-007, F-FWA-001
_FUNCTION_ID_RE = re.compile(r"\b[A-Z]-[A-Z]{3,}-\d{3,}\b")

# Pattern for acronyms (2–8 uppercase letters, optionally followed by digits)
_ACRONYM_RE = re.compile(r"\b[A-Z]{2,8}\d?\b")

# Pattern for numbers (integers, decimals, percentages)
_NUMBER_RE = re.compile(r"\b\d{2,}(?:[.,]\d+)?%?\b")

# Pattern for quoted phrases
_QUOTED_RE = re.compile(r'"([^"]{3,})"')


def _extract_claims(text: str, max_claims: int = 25) -> list[str]:
    """Extract verifiable claims from *text*.

    Returns a list of normalised claim strings (lowercased, stripped).
    """
    if not text:
        return []

    claims: list[str] = []
    seen: set[str] = set()

    def _add(claim: str) -> None:
        normalised = claim.strip().lower()
        if normalised and len(normalised) >= 2 and normalised not in seen:
            seen.add(normalised)
            claims.append(normalised)

    # 1. Function / requirement IDs (highest-evidence claims)
    for m in _FUNCTION_ID_RE.finditer(text):
        _add(m.group())

    # 2. Acronyms
    for m in _ACRONYM_RE.finditer(text):
        token = m.group()
        # Skip common English words that happen to be uppercase
        if token.upper() in {"THE", "AND", "FOR", "ARE", "WAS", "NOT", "BUT", "ALL", "CAN", "HAS", "ITS", "MAY", "PER"}:
            continue
        _add(token)

    # 3. Numbers (>= 2 digits, including percentages)
    for m in _NUMBER_RE.finditer(text):
        _add(m.group())

    # 4. Quoted phrases
    for m in _QUOTED_RE.finditer(text):
        phrase = m.group(1).strip()
        if len(phrase) >= 5:
            _add(phrase)

    # 5. Capitalised multi-word phrases (3–6 words, all starting with capital)
    cap_phrases = re.findall(
        r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,5}\b",
        text,
    )
    for phrase in cap_phrases:
        if len(phrase) >= 8:
            _add(phrase)

    return claims[:max_claims]


def _check_claim_in_chunks(claim: str, chunks: list[str]) -> bool:
    """Return True if *claim* appears in at least one chunk.

    Numbers are matched as exact tokens (boundary-aware) to avoid
    false positives like ``47`` matching ``470``.

    Short claims (<= 5 chars, typically acronyms) use a word-boundary
    regex to avoid false positives like ``"oms"`` matching ``"customs"``.
    Longer claims use substring matching since they are more specific.
    """
    if not chunks:
        return False

    is_number = bool(re.match(r"^\d{2,}(?:[.,]\d+)?%?$", claim))
    is_short = len(claim) <= 5

    for chunk in chunks:
        if not chunk:
            continue
        chunk_lower = chunk.lower()

        if is_number:
            # Token-level match for numbers
            tokens = set(chunk_lower.split())
            if claim in tokens:
                return True
        elif is_short:
            # Word-boundary match for short claims (acronyms like OMS, CRM)
            # Prevents false positives like "oms" matching inside "customs"
            pattern = re.compile(r"\b" + re.escape(claim) + r"\b")
            if pattern.search(chunk_lower):
                return True
        else:
            # Substring match for longer claims (phrases, quoted text)
            if claim in chunk_lower:
                return True

    return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def validate_grounding(
    answer_text: str,
    chunks: list[str],
    *,
    threshold: float = _GROUNDING_THRESHOLD,
    min_answer_length: int = _MIN_ANSWER_LENGTH,
    min_claims: int = _MIN_CLAIMS_FOR_REJECTION,
    filename: Optional[str] = None,
) -> dict:
    """Validate whether *answer_text* is grounded in the provided *chunks*.

    Parameters
    ----------
    answer_text : str
        The model-generated answer to validate.
    chunks : list[str]
        The retrieved context chunks (raw text of each chunk).
    threshold : float
        Minimum grounding fraction required (default 0.30 = 30 %).
    min_answer_length : int
        Answers shorter than this skip validation (default 50).
    min_claims : int
        Minimum number of claims required before rejection is possible.
    filename : str or None
        Optional source filename for richer log messages.

    Returns
    -------
    dict with keys:
        is_grounded : bool
            True when the answer passes the grounding check.
        score : float
            Fraction of claims that were found in chunks (0.0 – 1.0).
        total_claims : int
            Number of claims extracted.
        grounded_claims : int
            Number of claims found in at least one chunk.
        ungrounded_claims : list[str]
            Claims that were NOT found in any chunk.
        rejected : bool
            True when the answer was rejected (fails threshold).
        replacement : str or None
            The replacement answer when rejected, else None.
    """
    result: dict = {
        "is_grounded": True,
        "score": 1.0,
        "total_claims": 0,
        "grounded_claims": 0,
        "ungrounded_claims": [],
        "rejected": False,
        "replacement": None,
    }

    # ── Skip short answers (greetings, confirmations, etc.) ────────────
    if len(answer_text.strip()) < min_answer_length:
        logger.debug("[ANSWER_VALIDATOR] Skipped (too short: %d chars)", len(answer_text))
        result["is_grounded"] = True
        return result

    # ── Extract claims ──────────────────────────────────────────────────
    claims = _extract_claims(answer_text)
    if not claims:
        logger.debug("[ANSWER_VALIDATOR] No claims extracted — accepting answer")
        result["is_grounded"] = True
        return result

    result["total_claims"] = len(claims)

    # ── Check each claim ─────────────────────────────────────────────────
    grounded = 0
    ungrounded: list[str] = []
    for claim in claims:
        if _check_claim_in_chunks(claim, chunks):
            grounded += 1
        else:
            ungrounded.append(claim)

    result["grounded_claims"] = grounded
    result["ungrounded_claims"] = ungrounded

    score = grounded / len(claims) if claims else 1.0
    result["score"] = round(score, 4)

    source_tag = f" [{filename}]" if filename else ""

    # ── Accept / reject decision ────────────────────────────────────────
    if score >= threshold or len(claims) < min_claims:
        result["is_grounded"] = True
        logger.info(
            "[ANSWER_VALIDATOR] PASS%s — score=%.2f (threshold=%.2f) | "
            "claims=%d grounded=%d ungrounded=%s",
            source_tag, score, threshold,
            len(claims), grounded, ungrounded[:5],
        )
    else:
        result["is_grounded"] = False
        result["rejected"] = True
        result["replacement"] = (
            "I cannot find sufficient evidence in the uploaded documents "
            "to answer this question confidently. Please try rephrasing "
            "or providing more specific details."
        )
        logger.warning(
            "[ANSWER_VALIDATOR] REJECT%s — score=%.2f (threshold=%.2f) | "
            "claims=%d grounded=%d ungrounded=%s",
            source_tag, score, threshold,
            len(claims), grounded, ungrounded[:5],
        )

    return result
