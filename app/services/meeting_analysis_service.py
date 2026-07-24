"""
meeting_analysis_service.py — DocTel Meeting Intelligence Service

Analyzes audio/video transcripts and extracts structured meeting data:
- Meeting summary
- Agenda items
- Participants
- Key decisions
- Action items with owners
- Risks and issues
- Follow-up tasks
- Key dates
- Systems mentioned

Uses the existing DocTel LLM infrastructure (Gemini → DeepSeek → Ollama)
to process transcripts and return structured JSON output.
"""

import json
import logging
import re
from datetime import datetime, timezone
from typing import Optional, List
from dataclasses import dataclass, field, asdict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings

logger = logging.getLogger(__name__)


# ── Data Models ────────────────────────────────────────────────────────────


@dataclass
class MeetingParticipant:
    name: str
    role: Optional[str] = None
    speaking_percentage: Optional[float] = None


@dataclass
class AgendaItem:
    topic: str
    timestamp_sec: Optional[float] = None
    duration_sec: Optional[float] = None


@dataclass
class MeetingDecision:
    description: str
    made_by: Optional[str] = None
    timestamp_sec: Optional[float] = None
    consensus: bool = True


@dataclass
class ActionItem:
    action: str
    owner: Optional[str] = None
    due_date: Optional[str] = None
    priority: str = "Medium"  # High, Medium, Low
    status: str = "Open"


@dataclass
class MeetingRisk:
    risk: str
    impact: Optional[str] = None
    mitigation: Optional[str] = None
    severity: str = "Medium"  # High, Medium, Low


@dataclass
class FollowUp:
    task: str
    owner: Optional[str] = None
    next_meeting: bool = False


@dataclass
class MeetingResult:
    """Complete structured output from meeting analysis."""
    title: str = ""
    date: Optional[str] = None
    duration_minutes: Optional[float] = None
    summary: str = ""
    participants: List[MeetingParticipant] = field(default_factory=list)
    agenda: List[AgendaItem] = field(default_factory=list)
    topics_discussed: List[str] = field(default_factory=list)
    decisions: List[MeetingDecision] = field(default_factory=list)
    action_items: List[ActionItem] = field(default_factory=list)
    risks: List[MeetingRisk] = field(default_factory=list)
    follow_ups: List[FollowUp] = field(default_factory=list)
    key_dates: List[dict] = field(default_factory=list)
    systems_mentioned: List[str] = field(default_factory=list)
    entities: List[str] = field(default_factory=list)
    sentiment: str = "Neutral"


# ── Prompt Template ────────────────────────────────────────────────────────

MEETING_ANALYSIS_PROMPT = """You are a professional meeting analyst for ZETDC (Zimbabwe Electricity Transmission and Distribution Company).

Analyze the following meeting transcript and extract structured information.

Return ONLY a valid JSON object (no markdown, no commentary, no asterisks) with exactly these keys:

  title — string: A concise meeting title (max 15 words)
  summary — string: A professional 3-5 sentence narrative summary
  participants — array of objects: [{{"name": str, "role": str or null, "speaking_percentage": float or null}}]
  agenda — array of objects: [{{"topic": str, "timestamp_sec": float or null, "duration_sec": float or null}}]
  topics_discussed — array of strings (max 10)
  decisions — array of objects: [{{"description": str, "made_by": str or null, "timestamp_sec": float or null, "consensus": bool}}]
  action_items — array of objects: [{{"action": str, "owner": str or null, "due_date": str or null, "priority": "High"|"Medium"|"Low", "status": "Open"}}]
  risks — array of objects: [{{"risk": str, "impact": str or null, "mitigation": str or null, "severity": "High"|"Medium"|"Low"}}]
  follow_ups — array of objects: [{{"task": str, "owner": str or null, "next_meeting": bool}}]
  key_dates — array of objects: [{{"date": str, "event": str}}]
  systems_mentioned — array of strings (systems, applications, platforms discussed)
  entities — array of strings (people, departments, locations, vendors mentioned)
  sentiment — one of: "Positive", "Neutral", "Negative", "Urgent"

ANALYSIS RULES:
- Extract participants from speaker labels if available (e.g. "[Speaker 1]" or actual names)
- Identify decisions as specific commitments or agreements made during the meeting
- Each action item must be actionable — include owner and due date if mentioned
- List specific systems, applications, and platforms (e.g. OMS, CRM, ZUMS, SAP, SCADA)
- Use ZETDC terminology where applicable
- If a field has no data, use an empty array [] (not null)
- The summary must be flowing narrative prose — no bullet points, no asterisks

Transcript:
{transcript_text}"""


# ── Analysis Function ──────────────────────────────────────────────────────


async def analyze_meeting_transcript(
    transcript_text: str,
    db: AsyncSession,
    title_hint: Optional[str] = None,
    duration_minutes: Optional[float] = None,
) -> MeetingResult:
    """
    Analyze a meeting transcript and return structured MeetingResult.

    Uses the existing DocTel model resolution chain:
    Gemini API → DeepSeek API → Ollama local model

    Args:
        transcript_text: Full cleaned transcript text.
        db: Database session for model resolution.
        title_hint: Optional meeting title from filename.
        duration_minutes: Optional meeting duration.

    Returns:
        MeetingResult with all extracted fields.
    """
    # Cap transcript to stay within token limits
    max_chars = 12000
    analysis_text = transcript_text[:max_chars].strip()
    if len(transcript_text) > max_chars:
        logger.info("[MEETING] Transcript truncated to %d chars (original: %d)", max_chars, len(transcript_text))

    prompt = MEETING_ANALYSIS_PROMPT.format(transcript_text=analysis_text)
    structured: dict = {}

    # ── Try Gemini API first (superior analysis quality) ────────────────
    if settings.gemini_api_key:
        try:
            from app.services.gemini_service import generate as gemini_generate
            logger.info("[MEETING] Analyzing transcript with Gemini API")
            raw = await gemini_generate(
                prompt,
                system="You are a precise meeting analyst. Output only valid JSON.",
            )
            json_start = raw.find("{")
            json_end = raw.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                structured = json.loads(raw[json_start:json_end])
                logger.info("[MEETING] Gemini analysis successful")
        except Exception as e:
            logger.warning("[MEETING] Gemini analysis failed (%s); trying DeepSeek", e)

    # ── Try DeepSeek API if Gemini failed ──────────────────────────────
    if not structured and settings.deepseek_api_key:
        try:
            from app.services.deepseek_service import generate as deepseek_generate
            logger.info("[MEETING] Analyzing transcript with DeepSeek API")
            raw = await deepseek_generate(
                prompt,
                system="You are a precise meeting analyst. Output only valid JSON.",
            )
            json_start = raw.find("{")
            json_end = raw.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                structured = json.loads(raw[json_start:json_end])
                logger.info("[MEETING] DeepSeek analysis successful")
        except Exception as e:
            logger.warning("[MEETING] DeepSeek analysis failed (%s); falling back to Ollama", e)

    # ── Fallback to Ollama local model ─────────────────────────────────
    if not structured:
        try:
            from app.services.model_resolver_service import resolve_model
            resolved = await resolve_model(db, requested_model=None, task_type="summary")
            model_name = resolved["model_id"]

            from app.utils.ollama_client import ollama
            logger.info("[MEETING] Analyzing transcript with Ollama model: %s", model_name)
            raw = await ollama.generate(
                model_name,
                prompt,
                system="You are a precise meeting analyst. Output only valid JSON.",
                options={"num_ctx": 8192, "temperature": 0},
            )
            json_start = raw.find("{")
            json_end = raw.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                structured = json.loads(raw[json_start:json_end])
                logger.info("[MEETING] Ollama analysis successful")
        except Exception as e:
            logger.warning("[MEETING] Ollama analysis failed (%s); using extractive fallback", e)

    # ── Parse structured output into MeetingResult ─────────────────────
    result = MeetingResult()

    # Title
    result.title = str(structured.get("title", title_hint or "") or "").strip()
    if not result.title:
        result.title = title_hint or "Meeting Transcript"

    # Duration
    result.duration_minutes = duration_minutes

    # Summary
    result.summary = str(structured.get("summary", "") or "").strip()
    if not result.summary:
        # Extractive fallback: first few sentences
        sents = re.split(r"(?<=[.!?])\s+", analysis_text.replace("\n", " "))
        result.summary = " ".join(s[:200] for s in sents[:5]) if sents else "No summary available."

    # Participants
    raw_participants = structured.get("participants", [])
    if isinstance(raw_participants, list):
        for p in raw_participants:
            if isinstance(p, dict) and p.get("name"):
                result.participants.append(MeetingParticipant(
                    name=str(p["name"]),
                    role=str(p["role"]) if p.get("role") else None,
                    speaking_percentage=float(p["speaking_percentage"]) if p.get("speaking_percentage") is not None else None,
                ))

    # Agenda
    raw_agenda = structured.get("agenda", [])
    if isinstance(raw_agenda, list):
        for a in raw_agenda:
            if isinstance(a, dict) and a.get("topic"):
                result.agenda.append(AgendaItem(
                    topic=str(a["topic"]),
                    timestamp_sec=float(a["timestamp_sec"]) if a.get("timestamp_sec") is not None else None,
                    duration_sec=float(a["duration_sec"]) if a.get("duration_sec") is not None else None,
                ))

    # Topics
    raw_topics = structured.get("topics_discussed", [])
    if isinstance(raw_topics, list):
        result.topics_discussed = [str(t) for t in raw_topics if t]

    # Decisions
    raw_decisions = structured.get("decisions", [])
    if isinstance(raw_decisions, list):
        for d in raw_decisions:
            if isinstance(d, dict) and d.get("description"):
                result.decisions.append(MeetingDecision(
                    description=str(d["description"]),
                    made_by=str(d["made_by"]) if d.get("made_by") else None,
                    timestamp_sec=float(d["timestamp_sec"]) if d.get("timestamp_sec") is not None else None,
                    consensus=bool(d.get("consensus", True)),
                ))

    # Action items
    raw_actions = structured.get("action_items", [])
    if isinstance(raw_actions, list):
        for a in raw_actions:
            if isinstance(a, dict) and a.get("action"):
                result.action_items.append(ActionItem(
                    action=str(a["action"]),
                    owner=str(a["owner"]) if a.get("owner") else None,
                    due_date=str(a["due_date"]) if a.get("due_date") else None,
                    priority=str(a.get("priority", "Medium")),
                    status=str(a.get("status", "Open")),
                ))

    # Risks
    raw_risks = structured.get("risks", [])
    if isinstance(raw_risks, list):
        for r in raw_risks:
            if isinstance(r, dict) and r.get("risk"):
                result.risks.append(MeetingRisk(
                    risk=str(r["risk"]),
                    impact=str(r["impact"]) if r.get("impact") else None,
                    mitigation=str(r["mitigation"]) if r.get("mitigation") else None,
                    severity=str(r.get("severity", "Medium")),
                ))

    # Follow-ups
    raw_followups = structured.get("follow_ups", [])
    if isinstance(raw_followups, list):
        for f in raw_followups:
            if isinstance(f, dict) and f.get("task"):
                result.follow_ups.append(FollowUp(
                    task=str(f["task"]),
                    owner=str(f["owner"]) if f.get("owner") else None,
                    next_meeting=bool(f.get("next_meeting", False)),
                ))

    # Key dates
    raw_dates = structured.get("key_dates", [])
    if isinstance(raw_dates, list):
        result.key_dates = [{"date": str(d.get("date", "")), "event": str(d.get("event", ""))}
                           for d in raw_dates if isinstance(d, dict) and d.get("date")]

    # Systems mentioned
    raw_systems = structured.get("systems_mentioned", [])
    if isinstance(raw_systems, list):
        result.systems_mentioned = [str(s) for s in raw_systems if s]

    # Entities
    raw_entities = structured.get("entities", [])
    if isinstance(raw_entities, list):
        result.entities = [str(e) for e in raw_entities if e]

    # Sentiment
    sentiment = str(structured.get("sentiment", "") or "").strip().title()
    if sentiment in ("Positive", "Neutral", "Negative", "Urgent"):
        result.sentiment = sentiment
    else:
        result.sentiment = "Neutral"

    logger.info(
        "[MEETING] Analysis complete: title=%r, participants=%d, decisions=%d, actions=%d, risks=%d",
        result.title, len(result.participants), len(result.decisions),
        len(result.action_items), len(result.risks),
    )
    return result


# ── Serialization Helpers ─────────────────────────────────────────────────


def meeting_result_to_dict(result: MeetingResult) -> dict:
    """Convert MeetingResult to a JSON-serializable dict."""
    return {
        "title": result.title,
        "date": result.date,
        "duration_minutes": result.duration_minutes,
        "summary": result.summary,
        "participants": [asdict(p) for p in result.participants],
        "agenda": [asdict(a) for a in result.agenda],
        "topics_discussed": result.topics_discussed,
        "decisions": [asdict(d) for d in result.decisions],
        "action_items": [asdict(a) for a in result.action_items],
        "risks": [asdict(r) for r in result.risks],
        "follow_ups": [asdict(f) for f in result.follow_ups],
        "key_dates": result.key_dates,
        "systems_mentioned": result.systems_mentioned,
        "entities": result.entities,
        "sentiment": result.sentiment,
    }
