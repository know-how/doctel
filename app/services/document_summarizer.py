"""
document_summarizer.py — Enterprise Knowledge Base Summarization Engine

Transforms raw document text into structured, business-intelligence summaries
that answer "What does this document mean?" rather than "What text appears here?"

Supports document-type-aware templates:
  - Policy   → Objectives, Scope, Responsibilities, Compliance, Risks
  - FRS      → Business Overview, Requirements, Integrations, Actors, Workflows, Business Rules
  - Meeting  → Summary, Participants, Decisions, Action Items, Risks
  - SOP      → Purpose, Process Steps, Responsibilities, Controls
  - Generic  → Executive Summary, Key Findings, Responsibilities, Requirements, Risks, Actions
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# ── System prompt templates per document type ──────────────────────────────

POLICY_TEMPLATE = """You are a senior policy analyst at ZETDC.
Analyse the document below and return ONLY valid JSON with these keys:

  doc_type: "policy"
  executive_summary: string — narrative purpose, scope, and business context (max 8 sentences, no markdown, no bullets)
  key_findings: array of strings — most important findings as complete narrative sentences
  objectives: array of strings — policy objectives as complete sentences
  scope: string — who/what the policy covers
  responsibilities: array of objects with {"role": string, "department": string, "responsibility": string}
  compliance_requirements: array of strings — mandatory compliance obligations
  risks: array of objects with {"risk": string, "mitigation": string}
  actions: array of strings — required or recommended actions
  business_impact: string — operational and strategic importance
  systems_entities: array of objects with {"name": string, "type": "system"|"department"|"role"|"policy"|"location"}

RULES:
- NEVER use markdown formatting or asterisks
- Each string must be a complete, well-formed sentence
- Use professional ZETDC terminology
- If a section has no data, return an empty array or empty string"""

FRS_TEMPLATE = """You are a business analyst at ZETDC.
Analyse this Functional Requirements Specification and return ONLY valid JSON with these keys:

  doc_type: "frs"
  executive_summary: string — purpose, business context, and scope (max 8 sentences, no markdown)
  key_findings: array of strings — most important functional findings
  business_overview: string — what the system/process does and why it matters
  functional_requirements: array of strings — key requirements as complete sentences
  integrations: array of objects with {"system": string, "integration_type": string, "description": string}
  actors: array of strings — user roles and systems that interact
  workflows: array of objects with {"name": string, "steps": array of strings, "actors_involved": array of strings}
  business_rules: array of strings — business logic and validation rules
  responsibilities: array of objects with {"role": string, "department": string, "responsibility": string}
  risks: array of objects with {"risk": string, "mitigation": string}
  actions: array of strings — implementation or compliance actions
  business_impact: string — how this affects ZETDC operations
  systems_entities: array of objects with {"name": string, "type": "system"|"department"|"role"|"process"|"regulation"}

RULES:
- NEVER use markdown formatting or asterisks
- Each string must be a complete sentence
- Use precise ZETDC terminology
- If a section has no data, return an empty array or empty string"""

MEETING_TEMPLATE = """You are a meeting intelligence analyst at ZETDC.
Analyse this meeting transcript and return ONLY valid JSON with these keys:

  doc_type: "meeting"
  executive_summary: string — what was discussed and key outcomes (max 8 sentences, no markdown)
  key_findings: array of strings — most important findings as complete sentences
  meeting_purpose: string — purpose of the meeting
  participants: array of strings — named participants
  topics_discussed: array of strings — main discussion topics
  decisions: array of strings — decisions made during the meeting
  action_items: array of objects with {"owner": string, "action": string, "due_date": string or ""}
  risks: array of objects with {"risk": string, "owner": string}
  next_steps: array of strings — follow-up actions
  systems_entities: array of objects with {"name": string, "type": "system"|"department"|"person"|"project"}

RULES:
- NEVER use markdown formatting or asterisks
- Each string must be a complete sentence
- Use precise terminology
- If a section has no data, return an empty array or empty string"""

SOP_TEMPLATE = """You are a process analyst at ZETDC.
Analyse this Standard Operating Procedure and return ONLY valid JSON with these keys:

  doc_type: "sop"
  executive_summary: string — purpose and scope (max 8 sentences, no markdown)
  key_findings: array of strings — most important process findings
  purpose: string — why the procedure exists
  process_steps: array of objects with {"step_number": number, "step": string, "responsible": string}
  responsibilities: array of objects with {"role": string, "department": string, "responsibility": string}
  controls: array of strings — control measures and checkpoints
  risks: array of objects with {"risk": string, "mitigation": string, "severity": "high"|"medium"|"low"}
  actions: array of strings — required procedural actions
  systems_entities: array of objects with {"name": string, "type": "system"|"department"|"role"|"tool"}

RULES:
- NEVER use markdown formatting or asterisks
- Each string must be a complete sentence
- Use precise ZETDC terminology
- If a section has no data, return an empty array or empty string"""

GENERIC_TEMPLATE = """You are a senior document analyst at ZETDC.
Analyse the document below and return ONLY valid JSON with these keys:

  doc_type: "generic"
  executive_summary: string — purpose, scope, and business context (max 8 sentences, no markdown)
  key_findings: array of strings — most important findings as complete narrative sentences
  responsibilities: array of objects with {"role": string, "department": string, "responsibility": string}
  requirements: array of strings — key rules, controls, or mandatory actions
  risks: array of objects with {"risk": string, "mitigation": string}
  actions: array of strings — required or recommended actions
  business_impact: string — operational and strategic importance
  systems_entities: array of objects with {"name": string, "type": "system"|"department"|"role"|"policy"|"location"}

RULES:
- NEVER use markdown formatting or asterisks
- Each string must be a complete, well-formed sentence
- Use professional ZETDC terminology
- If a section has no data, return an empty array or empty string"""


def _select_template(doc_text: str, detected_type: str = "") -> str:
    """Select the most appropriate template based on document content and detected type."""
    lower = doc_text.lower()

    # If we already have a detected type from the ingestion pipeline, use it directly
    type_lower = detected_type.lower().strip()
    if type_lower in ("policy", "frs", "meeting", "sop", "generic"):
        template_map = {
            "policy": POLICY_TEMPLATE,
            "frs": FRS_TEMPLATE,
            "meeting": MEETING_TEMPLATE,
            "sop": SOP_TEMPLATE,
            "generic": GENERIC_TEMPLATE,
        }
        return template_map[type_lower]

    # Heuristic detection based on content patterns
    meeting_keywords = ["meeting", "agenda", "attendee", "participant", "minutes",
                        "discussion", "action item", "follow-up", "transcript",
                        "speaker 1", "speaker 2", "[00:"]
    policy_keywords = ["policy", "compliance", "regulation", "governance", "shall comply",
                       "must adhere", "responsible for", "scope of this policy"]
    frs_keywords = ["functional requirement", "system shall", "the system must",
                    "user story", "actor", "use case", "integration", "workflow",
                    "business rule", "frs", "requirements specification"]
    sop_keywords = ["standard operating procedure", "procedure", "process step",
                    "responsible", "control measure", "work instruction"]

    score_meeting = sum(2 for kw in meeting_keywords if kw in lower)
    score_policy = sum(2 for kw in policy_keywords if kw in lower)
    score_frs = sum(2 for kw in frs_keywords if kw in lower)
    score_sop = sum(2 for kw in sop_keywords if kw in lower)

    scores = [
        ("meeting", score_meeting),
        ("policy", score_policy),
        ("frs", score_frs),
        ("sop", score_sop),
    ]
    scores.sort(key=lambda x: -x[1])

    best_type, best_score = scores[0]

    # Require minimum score to auto-detect; otherwise use generic
    if best_score >= 4:
        templates = {
            "meeting": MEETING_TEMPLATE,
            "policy": POLICY_TEMPLATE,
            "frs": FRS_TEMPLATE,
            "sop": SOP_TEMPLATE,
        }
        return templates[best_type]

    return GENERIC_TEMPLATE


def _build_prompt(doc_text: str, filename: str = "", detected_type: str = "") -> str:
    """Build the full analysis prompt with the appropriate template."""
    template = _select_template(doc_text, detected_type)

    # Cap input text to avoid token limits — use the full document but stay within bounds
    # 12000 chars ≈ 3000 tokens, which should fit most models
    max_input_chars = 12000
    input_text = doc_text[:max_input_chars].strip()
    if len(doc_text) > max_input_chars:
        input_text += "\n\n[Document truncated due to length. Only the first portion was analysed.]"

    header = f"Document: {filename or 'Unknown'}\n\n"
    return header + "Document content:\n" + input_text + "\n\n" + template


def _extract_fallback_summary(doc_text: str, detected_type: str = "") -> dict[str, Any]:
    """Extractive fallback when LLM summarisation is unavailable.

    Produces a basic summary from first sentences and regex extraction.
    """
    sentences = [
        s.strip() for s in re.split(r"(?<=[.!?])\s+", doc_text.replace("\n", " "))
        if s.strip()
    ]

    exec_summary = " ".join(sentences[:5]) if sentences else "No content available."

    entities = []
    for m in re.finditer(r"\b[A-Z][A-Za-z]{2,}(?:\s+[A-Z][A-Za-z]{2,})*\b", doc_text):
        name = m.group().strip()
        if name and name not in entities:
            entities.append(name)

    return {
        "doc_type": detected_type or "generic",
        "executive_summary": exec_summary,
        "key_findings": sentences[5:10] if len(sentences) > 5 else sentences,
        "responsibilities": [],
        "risks": [],
        "actions": [],
        "business_impact": "",
        "systems_entities": [{"name": e, "type": "system"} for e in entities[:8]],
        "_fallback": True,
    }


def _clean_json(raw: str) -> str:
    """Extract and clean a JSON object from model output."""
    # Find the first { and last }
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        return raw[start:end + 1]

    # Try to find JSON code block
    json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
    if json_match:
        inner = json_match.group(1).strip()
        json_start = inner.find("{")
        json_end = inner.rfind("}")
        if json_start >= 0 and json_end > json_start:
            return inner[json_start:json_end + 1]

    return raw


def _normalize_result(result: dict[str, Any], doc_type_hint: str = "") -> dict[str, Any]:
    """Ensure all expected keys exist with correct types."""
    doc_type = result.get("doc_type", doc_type_hint or "generic")

    defaults: dict[str, Any] = {
        "doc_type": doc_type,
        "executive_summary": "",
        "key_findings": [],
        "business_impact": "",
        "systems_entities": [],
    }

    if doc_type == "policy":
        defaults.update({
            "objectives": [],
            "scope": "",
            "responsibilities": [],
            "compliance_requirements": [],
            "risks": [],
            "actions": [],
        })
    elif doc_type == "frs":
        defaults.update({
            "business_overview": "",
            "functional_requirements": [],
            "integrations": [],
            "actors": [],
            "workflows": [],
            "business_rules": [],
            "responsibilities": [],
            "risks": [],
            "actions": [],
        })
    elif doc_type == "meeting":
        defaults.update({
            "meeting_purpose": "",
            "participants": [],
            "topics_discussed": [],
            "decisions": [],
            "action_items": [],
            "risks": [],
            "next_steps": [],
        })
    elif doc_type == "sop":
        defaults.update({
            "purpose": "",
            "process_steps": [],
            "responsibilities": [],
            "controls": [],
            "risks": [],
            "actions": [],
        })
    else:
        defaults.update({
            "responsibilities": [],
            "requirements": [],
            "risks": [],
            "actions": [],
            "business_impact": "",
        })

    result = {**defaults, **result}
    # Ensure arrays are lists
    for k, v in result.items():
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    result[k] = parsed
            except (json.JSONDecodeError, TypeError):
                pass

    return result


async def generate_enterprise_summary(
    db: AsyncSession,
    doc_text: str,
    filename: str = "",
    detected_type: str = "",
) -> dict[str, Any]:
    """Generate a structured, document-type-aware enterprise summary.

    Uses Gemini → DeepSeek → Ollama fallback chain, with extractive fallback
    as last resort.
    """
    from app.config import settings
    from app.utils.ollama_client import ollama

    prompt = _build_prompt(doc_text, filename, detected_type)

    result: dict[str, Any] | None = None

    # ── Tier 1: Gemini API ──────────────────────────────────────────────
    if settings.gemini_api_key:
        try:
            from app.services.gemini_service import generate as gemini_generate
            logger.info("[SUMMARY] Generating enterprise summary with Gemini for %s", filename)
            raw = await gemini_generate(
                prompt,
                system="You are a precise document analyst. Output only valid JSON.",
                temperature=0.1,
            )
            cleaned = _clean_json(raw)
            result = json.loads(cleaned)
            logger.info("[SUMMARY] Gemini enterprise summary succeeded for %s", filename)
        except Exception as e:
            logger.warning("[SUMMARY] Gemini failed for %s: %s", filename, e)

    # ── Tier 2: DeepSeek API ───────────────────────────────────────────
    if result is None and settings.deepseek_api_key:
        try:
            from app.services.deepseek_service import generate as deepseek_generate
            logger.info("[SUMMARY] Falling back to DeepSeek for %s", filename)
            raw = await deepseek_generate(
                prompt,
                system="You are a precise document analyst. Output only valid JSON.",
            )
            cleaned = _clean_json(raw)
            result = json.loads(cleaned)
            logger.info("[SUMMARY] DeepSeek enterprise summary succeeded for %s", filename)
        except Exception as e:
            logger.warning("[SUMMARY] DeepSeek failed for %s: %s", filename, e)

    # ── Tier 3: Ollama local model ────────────────────────────────────
    if result is None:
        try:
            # Resolve model for summary task
            from app.services.model_resolver_service import resolve_model
            resolved = await resolve_model(db, requested_model=None, task_type="summary")
            model_name = resolved.get("model_id", "qwen3:4b")

            logger.info("[SUMMARY] Falling back to Ollama (%s) for %s", model_name, filename)
            raw = await ollama.generate(
                model_name,
                prompt,
                system="You are a precise document analyst. Output only valid JSON.",
                options={"num_ctx": 8192, "temperature": 0.1},
            )
            cleaned = _clean_json(raw)
            result = json.loads(cleaned)
            logger.info("[SUMMARY] Ollama enterprise summary succeeded for %s", filename)
        except Exception as e:
            logger.warning("[SUMMARY] Ollama failed for %s: %s", filename, e)

    # ── Fallback: extractive ───────────────────────────────────────────
    if result is None:
        logger.warning("[SUMMARY] All LLM providers failed for %s; using extractive fallback", filename)
        result = _extract_fallback_summary(doc_text, detected_type)
        return _normalize_result(result, detected_type)

    return _normalize_result(result, detected_type)
