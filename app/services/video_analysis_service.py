"""
video_analysis_service.py — DocTel Media Intelligence Layer

Unified video analysis that produces structured intelligence from video content.

Capabilities:
  - Audio extraction + transcription (reuses transcription_router_service)
  - Key frame extraction at configurable intervals
  - Scene/slide/screen detection via vision models
  - Visual entity extraction (people, objects, UI elements, text)
  - Meeting intelligence (decisions, actions, slides, participants)
  - Training analysis (procedures, workflows, knowledge checks)
  - System demo analysis (UI flows, buttons, screens, processes)
  - Timeline generation with visual events

Architecture:

  analyze_video(file_path)
    ↓
  extract_audio() ──→ transcribe() ──→ transcript + segments
    ↓
  extract_frames() ──→ analyze_frames() ──→ visual_events
    ↓
  build_video_intelligence()
    ↓
  VideoIntelligenceResult
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import math
import os
import subprocess
import tempfile
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


# ── Enums ─────────────────────────────────────────────────────────────────


class VideoType(str, Enum):
    """Classification of video content type."""
    MEETING = "meeting"
    TRAINING = "training"
    SYSTEM_DEMO = "system_demo"
    PRESENTATION = "presentation"
    RECORDING = "recording"
    OTHER = "other"


class FrameAnalysisType(str, Enum):
    """Type of visual content detected in a frame."""
    SLIDE = "slide"
    SCREEN = "screen"
    PERSON = "person"
    DOCUMENT = "document"
    DIAGRAM = "diagram"
    UI = "ui"
    WHITEBOARD = "whiteboard"
    OTHER = "other"


# ── Data Classes ──────────────────────────────────────────────────────────


@dataclass
class VideoFrame:
    """A single extracted frame from the video."""
    timestamp_sec: float
    image_path: str
    analysis_type: FrameAnalysisType = FrameAnalysisType.OTHER
    description: str = ""
    text_detected: str = ""
    confidence: float = 0.0


@dataclass
class VisualEvent:
    """A visual event detected in the video (slide change, person appears, etc.)."""
    timestamp_sec: float
    event_type: str  # slide_change | screen_transition | person_appears | ui_action
    description: str = ""
    frame_path: str = ""
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class VideoIntelligenceResult:
    """Complete video intelligence output."""
    # Core metadata
    filename: str = ""
    duration_sec: float = 0.0
    video_type: VideoType = VideoType.OTHER
    width: int = 0
    height: int = 0
    fps: float = 0.0
    codec: str = ""

    # Transcript
    transcript: str = ""
    transcription_engine: str = ""
    transcription_confidence: float = 0.0
    segments: list[dict] = field(default_factory=list)

    # Visual analysis
    frames_analyzed: int = 0
    visual_events: list[dict] = field(default_factory=list)
    screens_detected: list[dict] = field(default_factory=list)
    slides_detected: list[dict] = field(default_factory=list)
    people_detected: list[str] = field(default_factory=list)
    ui_elements: list[str] = field(default_factory=list)

    # Meeting intelligence
    participants: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    decisions: list[dict] = field(default_factory=list)
    action_items: list[dict] = field(default_factory=list)
    risks: list[dict] = field(default_factory=list)
    follow_ups: list[dict] = field(default_factory=list)
    slides_reviewed: list[str] = field(default_factory=list)
    documents_referenced: list[str] = field(default_factory=list)

    # Training intelligence
    procedures: list[dict] = field(default_factory=list)
    workflows: list[dict] = field(default_factory=list)
    steps_found: list[str] = field(default_factory=list)
    knowledge_checks: list[str] = field(default_factory=list)

    # System demo intelligence
    ui_flows: list[dict] = field(default_factory=list)
    buttons_detected: list[str] = field(default_factory=list)
    forms_detected: list[str] = field(default_factory=list)
    business_processes: list[str] = field(default_factory=list)

    # Entity extraction
    people: list[str] = field(default_factory=list)
    systems: list[str] = field(default_factory=list)
    policies: list[str] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)

    # Timeline
    timeline: list[dict] = field(default_factory=list)

    # Metadata
    analysis_time_ms: int = 0
    error: Optional[str] = None


# ── FFmpeg Helpers ────────────────────────────────────────────────────────


def _has_ffmpeg() -> bool:
    """Check if ffmpeg is available on PATH."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True, text=True, timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


def _has_ffprobe() -> bool:
    """Check if ffprobe is available on PATH."""
    try:
        result = subprocess.run(
            ["ffprobe", "-version"],
            capture_output=True, text=True, timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


def _get_video_info(video_path: str) -> dict[str, Any]:
    """Extract video metadata using ffprobe."""
    info: dict[str, Any] = {
        "duration_sec": 0.0,
        "width": 0,
        "height": 0,
        "fps": 0.0,
        "codec": "",
    }
    if not _has_ffprobe():
        return info

    try:
        # Duration
        dur_result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "format=duration", "-of",
             "default=noprint_wrappers=1:nokey=1",
             video_path],
            capture_output=True, text=True, timeout=10,
        )
        if dur_result.returncode == 0 and dur_result.stdout.strip():
            info["duration_sec"] = float(dur_result.stdout.strip())

        # Video stream info
        stream_result = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height,codec_name,r_frame_rate",
             "-of", "json", video_path],
            capture_output=True, text=True, timeout=10,
        )
        if stream_result.returncode == 0 and stream_result.stdout.strip():
            stream_data = json.loads(stream_result.stdout)
            streams = stream_data.get("streams", [])
            if streams:
                s = streams[0]
                info["width"] = s.get("width", 0)
                info["height"] = s.get("height", 0)
                info["codec"] = s.get("codec_name", "")
                # Parse frame rate (e.g. "30000/1001" -> 29.97)
                fps_str = s.get("r_frame_rate", "0/1")
                if "/" in fps_str:
                    num, den = fps_str.split("/")
                    try:
                        info["fps"] = float(num) / float(den) if float(den) > 0 else 0.0
                    except (ValueError, ZeroDivisionError):
                        info["fps"] = 0.0
    except Exception as e:
        logger.warning("[VIDEO] ffprobe error: %s", e)

    return info


def _extract_audio_from_video(
    video_path: str, output_path: Optional[str] = None
) -> Optional[str]:
    """Extract audio track from video file into WAV format."""
    if not _has_ffmpeg():
        logger.warning("[VIDEO] ffmpeg not available — cannot extract audio")
        return None

    if output_path is None:
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        output_path = tmp.name
        tmp.close()

    try:
        result = subprocess.run(
            [
                "ffmpeg", "-i", video_path,
                "-vn", "-acodec", "pcm_s16le",
                "-ar", "16000", "-ac", "1",
                "-y", output_path,
            ],
            capture_output=True, text=True, timeout=300,
        )
        if result.returncode == 0 and Path(output_path).exists():
            logger.info("[VIDEO] Audio extracted to %s", output_path)
            return output_path
        logger.warning("[VIDEO] Audio extraction failed: %s", result.stderr[:200])
        return None
    except Exception as e:
        logger.warning("[VIDEO] Audio extraction exception: %s", e)
        return None


def _extract_frames(
    video_path: str,
    interval_sec: float = 10.0,
    max_frames: int = 50,
    output_dir: Optional[str] = None,
) -> list[VideoFrame]:
    """Extract key frames from video at regular intervals.

    Uses ffmpeg to extract frames every `interval_sec` seconds.
    Limits total frames to `max_frames`.
    Returns list of VideoFrame objects with timestamp and path.
    """
    if not _has_ffmpeg():
        logger.warning("[VIDEO] ffmpeg not available — cannot extract frames")
        return []

    if output_dir is None:
        output_dir_obj = tempfile.mkdtemp(prefix="video_frames_")
        output_dir = output_dir_obj
    else:
        Path(output_dir).mkdir(parents=True, exist_ok=True)

    frames: list[VideoFrame] = []
    info = _get_video_info(video_path)
    duration = info.get("duration_sec", 0.0)
    if duration <= 0:
        logger.warning("[VIDEO] Cannot determine duration for frame extraction")
        return []

    # Calculate timestamps
    timestamps = [i * interval_sec for i in range(int(duration / interval_sec) + 1)]
    if len(timestamps) > max_frames:
        # Sample evenly if too many frames
        step = len(timestamps) / max_frames
        timestamps = [timestamps[min(int(i * step), len(timestamps) - 1)]
                      for i in range(max_frames)]

    for i, ts in enumerate(timestamps):
        out_path = os.path.join(output_dir, f"frame_{i:04d}.jpg")

        try:
            result = subprocess.run(
                [
                    "ffmpeg", "-ss", str(ts),
                    "-i", video_path,
                    "-vframes", "1",
                    "-q:v", "2",
                    "-y", out_path,
                ],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0 and Path(out_path).exists():
                frames.append(VideoFrame(
                    timestamp_sec=ts,
                    image_path=out_path,
                ))
        except Exception as e:
            logger.warning("[VIDEO] Frame extraction failed at t=%.1f: %s", ts, e)

    logger.info("[VIDEO] Extracted %d frames from %s", len(frames), video_path)
    return frames


# ── Frame Analysis ────────────────────────────────────────────────────────


async def _analyze_frame_ollama(
    image_path: str, prompt: str
) -> Optional[str]:
    """Analyze a single frame using Ollama vision model."""
    if not settings.vision_model:
        return None

    try:
        with open(image_path, "rb") as f:
            image_b64 = base64.b64encode(f.read()).decode("utf-8")
    except Exception as e:
        logger.warning("[VIDEO] Frame read error: %s", e)
        return None

    url = f"{settings.ollama_base_url.rstrip('/')}/api/generate"
    payload = {
        "model": settings.vision_model,
        "prompt": prompt,
        "images": [image_b64],
        "stream": False,
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            text = resp.json().get("response", "").strip()
            return text if text else None
    except Exception as e:
        logger.warning("[VIDEO] Ollama vision error: %s", e)
        return None


async def _analyze_frame_gemini(
    image_path: str, prompt: str
) -> Optional[str]:
    """Analyze a frame using Gemini vision."""
    try:
        from app.services.gemini_service import analyze_image as gemini_analyze
        if _gemini_is_configured():
            return await gemini_analyze(image_path, prompt)
    except Exception as e:
        logger.warning("[VIDEO] Gemini vision error: %s", e)
    return None


def _gemini_is_configured() -> bool:
    """Check if Gemini is configured."""
    try:
        from app.services.gemini_service import is_configured
        return is_configured()
    except Exception:
        return False


async def _analyze_frame(
    image_path: str,
    prompt: str,
    use_gemini: bool = False,
) -> Optional[str]:
    """Analyze a single frame using best available vision model.

    Priority: configured vision model (Ollama) → Gemini.
    """
    # Try Ollama first
    result = await _analyze_frame_ollama(image_path, prompt)
    if result:
        return result

    # Fallback to Gemini
    if use_gemini:
        return await _analyze_frame_gemini(image_path, prompt)

    return None


async def _classify_frame_type(image_path: str) -> FrameAnalysisType:
    """Classify the type of content in a frame."""
    prompt = (
        "Classify this image into ONE of the following categories:\n"
        "- slide: A presentation slide with text, bullet points, or charts\n"
        "- screen: A computer screen, UI, or software interface\n"
        "- person: One or more people visible\n"
        "- document: A document, PDF, or paper being shown\n"
        "- diagram: A technical diagram, flowchart, or architecture\n"
        "- ui: User interface element, form, or application screen\n"
        "- whiteboard: Whiteboard with handwritten content\n"
        "- other: None of the above\n\n"
        "Respond with ONLY the category name, nothing else."
    )
    result = await _analyze_frame(image_path, prompt)
    if result:
        result_lower = result.strip().lower()
        for atype in FrameAnalysisType:
            if atype.value == result_lower:
                return atype
    return FrameAnalysisType.OTHER


async def _describe_frame(image_path: str) -> str:
    """Generate a textual description of a frame."""
    prompt = (
        "Describe what is shown in this image in 1-2 sentences. "
        "Focus on: what type of content (slide, screen, person, document, diagram), "
        "any visible text or UI elements, and the general purpose."
    )
    result = await _analyze_frame(image_path, prompt, use_gemini=True)
    return result or "Frame could not be analyzed"


async def _extract_text_from_frame(image_path: str) -> str:
    """Extract visible text from a frame using vision model."""
    prompt = (
        "Extract ALL visible text from this image. "
        "Preserve formatting, bullet points, and structure. "
        "If the image contains a slide, extract all slide content. "
        "If the image contains a UI, extract all button labels and field names. "
        "If no text is visible, respond with '[No text visible]'."
    )
    result = await _analyze_frame(image_path, prompt, use_gemini=True)
    return result or ""


# ── Video Intelligence Analysis ──────────────────────────────────────────


async def _detect_visual_events(
    frames: list[VideoFrame],
    video_path: str,
) -> list[VisualEvent]:
    """Detect significant visual events across frames.

    Compares consecutive frames to identify:
    - Slide changes (significant content change)
    - Screen transitions
    - Person appearances
    """
    events: list[VisualEvent] = []
    previous_classification: Optional[str] = None

    for frame in frames:
        # Classify the frame
        ftype = await _classify_frame_type(frame.image_path)

        # Detect classification changes
        ftype_str = ftype.value
        if previous_classification and ftype_str != previous_classification:
            events.append(VisualEvent(
                timestamp_sec=frame.timestamp_sec,
                event_type=f"{previous_classification}_to_{ftype_str}",
                description=f"Transition from {previous_classification} to {ftype_str}",
                frame_path=frame.image_path,
                confidence=0.7,
            ))

        # Detect slides
        if ftype == FrameAnalysisType.SLIDE:
            text = await _extract_text_from_frame(frame.image_path)
            if text and len(text) > 20:
                events.append(VisualEvent(
                    timestamp_sec=frame.timestamp_sec,
                    event_type="slide_content",
                    description=f"Slide at {frame.timestamp_sec:.0f}s: {text[:100]}...",
                    frame_path=frame.image_path,
                    confidence=0.8,
                    metadata={"text": text},
                ))

        # Detect UI/screens
        if ftype == FrameAnalysisType.SCREEN or ftype == FrameAnalysisType.UI:
            description = await _describe_frame(frame.image_path)
            events.append(VisualEvent(
                timestamp_sec=frame.timestamp_sec,
                event_type="screen_capture",
                description=description,
                frame_path=frame.image_path,
                confidence=0.7,
            ))

        # Detect people
        if ftype == FrameAnalysisType.PERSON:
            events.append(VisualEvent(
                timestamp_sec=frame.timestamp_sec,
                event_type="person_visible",
                description=f"Person(s) visible at {frame.timestamp_sec:.0f}s",
                frame_path=frame.image_path,
                confidence=0.6,
            ))

        # Detect diagrams
        if ftype == FrameAnalysisType.DIAGRAM:
            description = await _describe_frame(frame.image_path)
            events.append(VisualEvent(
                timestamp_sec=frame.timestamp_sec,
                event_type="diagram",
                description=description,
                frame_path=frame.image_path,
                confidence=0.8,
            ))

        previous_classification = ftype_str

    return events


async def _generate_timeline(
    transcript: str,
    segments: list[dict],
    visual_events: list[VisualEvent],
    duration_sec: float,
) -> list[dict]:
    """Generate a combined timeline from transcript segments and visual events.

    Merges transcript segments with visual events chronologically.
    """
    timeline: list[dict] = []

    # Add transcript segments as timeline entries
    for seg in segments:
        timeline.append({
            "timestamp_sec": seg.get("start_sec", 0.0),
            "end_sec": seg.get("end_sec", 0.0),
            "type": "transcript",
            "content": seg.get("text", ""),
            "speaker": seg.get("speaker"),
        })

    # Add visual events
    for evt in visual_events:
        timeline.append({
            "timestamp_sec": evt.timestamp_sec,
            "end_sec": evt.timestamp_sec + 1.0,
            "type": evt.event_type,
            "content": evt.description,
            "frame_path": evt.frame_path,
        })

    # Sort chronologically
    timeline.sort(key=lambda e: e["timestamp_sec"])
    return timeline


async def _extract_entities_from_transcript(
    transcript: str,
) -> dict[str, list[str]]:
    """Extract entities from transcript using Ollama analysis."""
    if not transcript or len(transcript) < 50:
        return {
            "people": [],
            "systems": [],
            "policies": [],
            "entities": [],
            "locations": [],
        }

    prompt = (
        f"Extract key entities from the following video transcript. "
        f"Return a JSON object with these keys: "
        f"people (list of person names), systems (list of system/software names), "
        f"policies (list of policy/document names), "
        f"entities (list of key business entities), "
        f"locations (list of locations mentioned).\n\n"
        f"Transcript:\n{transcript[:3000]}"
    )

    try:
        # Try Ollama for extraction
        from app.services.opencode_zen_service import generate as zen_gen
        response = await zen_gen(prompt)
        if response:
            # Try to parse JSON from response
            import re as _re
            json_match = _re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, _re.DOTALL)
            if json_match:
                return json.loads(json_match.group(1))
            # Try direct JSON parse
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                pass
    except Exception as e:
        logger.warning("[VIDEO] Entity extraction error: %s", e)

    return {
        "people": [],
        "systems": [],
        "policies": [],
        "entities": [],
        "locations": [],
    }


async def _classify_video_content(
    transcript: str,
    visual_events: list[VisualEvent],
    frames: list[VideoFrame],
) -> VideoType:
    """Classify the video content type based on transcript and visual analysis.

    Uses keyword/pattern matching on transcript + frame classification counts.
    """
    lower_transcript = transcript.lower()

    # Meeting indicators
    meeting_keywords = [
        "meeting", "agenda", "discuss", "attendee", "participant",
        "minutes", "workshop", "update", "decision", "action item",
        "let's start", "next agenda", "any questions", "follow up",
    ]
    meeting_score = sum(1 for kw in meeting_keywords if kw in lower_transcript)

    # Training indicators
    training_keywords = [
        "training", "tutorial", "learn", "demonstration", "step",
        "how to", "walk through", "walkthrough", "guide", "practice",
        "knowledge check", "exercise", "module", "lesson",
    ]
    training_score = sum(1 for kw in training_keywords if kw in lower_transcript)

    # System demo indicators
    demo_keywords = [
        "login", "dashboard", "click", "button", "menu", "navigate",
        "system", "application", "interface", "screen", "workflow",
        "form", "field", "submit", "save", "create new", "search",
    ]
    demo_score = sum(1 for kw in demo_keywords if kw in lower_transcript)

    # Frame type analysis — events can be VisualEvent objects or dicts
    def _event_type(e):
        return e.event_type if hasattr(e, 'event_type') else e.get('event_type', '')
    slide_count = sum(1 for e in visual_events if _event_type(e) == 'slide_content')
    screen_count = sum(1 for e in visual_events if _event_type(e) == 'screen_capture')

    # Weighted scoring
    scores = {
        VideoType.MEETING: meeting_score * 1.5,
        VideoType.TRAINING: training_score * 1.5 + slide_count * 0.5,
        VideoType.SYSTEM_DEMO: demo_score * 2.0 + screen_count * 1.0,
        VideoType.PRESENTATION: slide_count * 1.5,
    }

    best_type = max(scores, key=scores.get)
    if scores[best_type] < 2:
        return VideoType.RECORDING
    return best_type


async def _generate_meeting_intelligence(
    transcript: str,
    events: list[VisualEvent],
) -> dict[str, Any]:
    """Extract meeting-specific intelligence (decisions, actions, risks, etc.)."""
    intelligence: dict[str, Any] = {
        "participants": [],
        "topics": [],
        "decisions": [],
        "action_items": [],
        "risks": [],
        "follow_ups": [],
        "slides_reviewed": [],
        "documents_referenced": [],
    }

    if not transcript or len(transcript) < 100:
        return intelligence

    prompt = (
        f"Analyze the following meeting transcript and extract structured information. "
        f"Return a JSON object with these keys:\n"
        f"- participants: list of people who spoke or were mentioned\n"
        f"- topics: list of main discussion topics\n"
        f"- decisions: list of dicts with {{'decision': str, 'made_by': str, 'context': str}}\n"
        f"- action_items: list of dicts with {{'action': str, 'owner': str, 'due_date': str, 'priority': str}}\n"
        f"- risks: list of dicts with {{'risk': str, 'impact': str, 'mitigation': str}}\n"
        f"- follow_ups: list of dicts with {{'item': str, 'owner': str}}\n"
        f"- slides_reviewed: list of slide titles mentioned\n"
        f"- documents_referenced: list of document names referenced\n\n"
        f"Transcript:\n{transcript[:5000]}"
    )

    try:
        from app.services.opencode_zen_service import generate as zen_gen
        response = await zen_gen(prompt)
        if response:
            import re as _re
            json_match = _re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, _re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group(1))
                intelligence.update(parsed)
            else:
                try:
                    parsed = json.loads(response)
                    intelligence.update(parsed)
                except json.JSONDecodeError:
                    pass
    except Exception as e:
        logger.warning("[VIDEO] Meeting intelligence error: %s", e)

    return intelligence


async def _generate_training_intelligence(
    transcript: str,
    events: list[VisualEvent],
) -> dict[str, Any]:
    """Extract training-specific intelligence (procedures, steps, knowledge checks)."""
    intelligence: dict[str, Any] = {
        "procedures": [],
        "workflows": [],
        "steps_found": [],
        "knowledge_checks": [],
    }

    if not transcript or len(transcript) < 100:
        return intelligence

    prompt = (
        f"Analyze the following training video transcript. "
        f"Return a JSON object with these keys:\n"
        f"- procedures: list of procedures mentioned (each: {{'name': str, 'description': str}})\n"
        f"- workflows: list of dicts with {{'name': str, 'steps': [str]}}\n"
        f"- steps_found: list of individual step descriptions\n"
        f"- knowledge_checks: list of quiz questions or knowledge check topics\n\n"
        f"Transcript:\n{transcript[:4000]}"
    )

    try:
        from app.services.opencode_zen_service import generate as zen_gen
        response = await zen_gen(prompt)
        if response:
            import re as _re
            json_match = _re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, _re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group(1))
                intelligence.update(parsed)
            else:
                try:
                    parsed = json.loads(response)
                    intelligence.update(parsed)
                except json.JSONDecodeError:
                    pass
    except Exception as e:
        logger.warning("[VIDEO] Training intelligence error: %s", e)

    return intelligence


async def _generate_demo_intelligence(
    transcript: str,
    events: list[VisualEvent],
) -> dict[str, Any]:
    """Extract system demo-specific intelligence (UI flows, buttons, forms)."""
    intelligence: dict[str, Any] = {
        "ui_flows": [],
        "buttons_detected": [],
        "forms_detected": [],
        "business_processes": [],
    }

    if not transcript or len(transcript) < 100:
        return intelligence

    prompt = (
        f"Analyze the following system demonstration transcript. "
        f"Return a JSON object with these keys:\n"
        f"- ui_flows: list of dicts with {{'flow_name': str, 'steps': [str], 'system': str}}\n"
        f"- buttons_detected: list of button labels or UI controls mentioned\n"
        f"- forms_detected: list of form names or data entry screens\n"
        f"- business_processes: list of business processes demonstrated\n\n"
        f"Transcript:\n{transcript[:4000]}"
    )

    try:
        from app.services.opencode_zen_service import generate as zen_gen
        response = await zen_gen(prompt)
        if response:
            import re as _re
            json_match = _re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, _re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group(1))
                intelligence.update(parsed)
            else:
                try:
                    parsed = json.loads(response)
                    intelligence.update(parsed)
                except json.JSONDecodeError:
                    pass
    except Exception as e:
        logger.warning("[VIDEO] Demo intelligence error: %s", e)

    return intelligence


# ── Main Analysis Pipeline ────────────────────────────────────────────────


async def analyze_video(
    video_path: str,
    mime_type: Optional[str] = None,
    engine: Optional[str] = None,
    max_frames: int = 50,
    frame_interval_sec: float = 15.0,
    analyze_frames: bool = True,
) -> VideoIntelligenceResult:
    """Analyze a video file and produce comprehensive VideoIntelligenceResult.

    This is the primary entry point. It:
    1. Extracts video metadata (duration, resolution, codec, fps)
    2. Extracts audio and transcribes it
    3. Extracts key frames at regular intervals
    4. Analyzes frames for visual content (slides, screens, people, etc.)
    5. Classifies the video type (meeting, training, demo, etc.)
    6. Generates type-specific intelligence
    7. Builds a combined timeline
    8. Extracts entities

    Parameters
    ----------
    video_path : str
        Path to the video file.
    mime_type : str or None
        MIME type for Gemini API.
    engine : str or None
        Transcription engine: "faster_whisper", "gemini", "hybrid".
        If None, uses default from transcription_router_service.
    max_frames : int
        Maximum number of frames to extract and analyze (default 50).
    frame_interval_sec : float
        Interval in seconds between extracted frames (default 15).
    analyze_frames : bool
        Whether to perform visual frame analysis (default True).

    Returns
    -------
    VideoIntelligenceResult
        Complete video intelligence output.
    """
    start_time = time.time()
    filename = Path(video_path).name

    result = VideoIntelligenceResult(filename=filename)

    if not Path(video_path).exists():
        result.error = f"Video file not found: {video_path}"
        return result

    # ── Step 1: Extract video metadata ────────────────────────────────────
    info = _get_video_info(video_path)
    result.duration_sec = info.get("duration_sec", 0.0)
    result.width = info.get("width", 0)
    result.height = info.get("height", 0)
    result.fps = info.get("fps", 0.0)
    result.codec = info.get("codec", "")
    logger.info("[VIDEO] Analyzing %s (%.0fs, %dx%d, %.1ffps, %s)",
                filename, result.duration_sec, result.width, result.height,
                result.fps, result.codec)

    # ── Step 2: Extract audio and transcribe ──────────────────────────────
    audio_path = _extract_audio_from_video(video_path)
    if audio_path:
        try:
            from app.services.transcription_router_service import (
                transcribe_audio as route_transcribe,
            )

            tx_result = await route_transcribe(
                audio_path,
                mime_type="audio/wav",
                engine=engine,
            )
            if tx_result and tx_result.full_text:
                result.transcript = tx_result.full_text
                result.transcription_engine = tx_result.engine
                result.transcription_confidence = tx_result.confidence
                result.segments = [
                    {
                        "start_sec": s.start_sec,
                        "end_sec": s.end_sec,
                        "text": s.text,
                        "confidence": s.confidence,
                        "speaker": s.speaker,
                        "language": s.language,
                    }
                    for s in tx_result.segments
                ]
                logger.info("[VIDEO] Transcription complete: %d chars, engine=%s",
                            len(tx_result.full_text), tx_result.engine)
        except Exception as e:
            logger.warning("[VIDEO] Transcription error: %s", e)
        finally:
            # Cleanup temp audio file
            try:
                if audio_path and audio_path != video_path:
                    Path(audio_path).unlink(missing_ok=True)
            except Exception:
                pass

    # ── Step 3: Extract and analyze frames ────────────────────────────────
    if analyze_frames:
        temp_frame_dir = tempfile.mkdtemp(prefix="video_frames_")
        try:
            frames = _extract_frames(
                video_path,
                interval_sec=frame_interval_sec,
                max_frames=max_frames,
                output_dir=temp_frame_dir,
            )
            result.frames_analyzed = len(frames)

            if frames:
                # Detect visual events
                visual_events = await _detect_visual_events(frames, video_path)
                result.visual_events = [asdict(e) for e in visual_events]

                # Extract screens and slides
                result.slides_detected = [
                    {
                        "timestamp_sec": e.timestamp_sec,
                        "content": e.metadata.get("text", e.description),
                        "frame_path": e.frame_path,
                    }
                    for e in visual_events
                    if e.event_type in ("slide_content",)
                ]
                result.screens_detected = [
                    {
                        "timestamp_sec": e.timestamp_sec,
                        "description": e.description,
                        "frame_path": e.frame_path,
                    }
                    for e in visual_events
                    if e.event_type == "screen_capture"
                ]
        except Exception as e:
            logger.warning("[VIDEO] Frame analysis error: %s", e)
        finally:
            # Cleanup frame directory
            try:
                import shutil
                shutil.rmtree(temp_frame_dir, ignore_errors=True)
            except Exception:
                pass

    # ── Step 4: Classify video type ───────────────────────────────────────
    result.video_type = await _classify_video_content(
        result.transcript,
        result.visual_events,
        result.visual_events,  # Pass events as frame substitutes
    )
    logger.info("[VIDEO] Classified as: %s", result.video_type.value)

    # ── Step 5: Generate type-specific intelligence ───────────────────────
    if result.video_type == VideoType.MEETING and result.transcript:
        meeting_data = await _generate_meeting_intelligence(
            result.transcript, result.visual_events
        )
        result.participants = meeting_data.get("participants", [])
        result.topics = meeting_data.get("topics", [])
        result.decisions = meeting_data.get("decisions", [])
        result.action_items = meeting_data.get("action_items", [])
        result.risks = meeting_data.get("risks", [])
        result.follow_ups = meeting_data.get("follow_ups", [])
        result.slides_reviewed = meeting_data.get("slides_reviewed", [])
        result.documents_referenced = meeting_data.get("documents_referenced", [])

    elif result.video_type == VideoType.TRAINING and result.transcript:
        training_data = await _generate_training_intelligence(
            result.transcript, result.visual_events
        )
        result.procedures = training_data.get("procedures", [])
        result.workflows = training_data.get("workflows", [])
        result.steps_found = training_data.get("steps_found", [])
        result.knowledge_checks = training_data.get("knowledge_checks", [])

    elif result.video_type == VideoType.SYSTEM_DEMO and result.transcript:
        demo_data = await _generate_demo_intelligence(
            result.transcript, result.visual_events
        )
        result.ui_flows = demo_data.get("ui_flows", [])
        result.buttons_detected = demo_data.get("buttons_detected", [])
        result.forms_detected = demo_data.get("forms_detected", [])
        result.business_processes = demo_data.get("business_processes", [])

    # ── Step 6: Extract entities ──────────────────────────────────────────
    if result.transcript:
        entities_data = await _extract_entities_from_transcript(result.transcript)
        result.people = entities_data.get("people", [])
        result.systems = entities_data.get("systems", [])
        result.policies = entities_data.get("policies", [])
        result.entities = entities_data.get("entities", [])
        result.locations = entities_data.get("locations", [])

    # ── Step 7: Build timeline ────────────────────────────────────────────
    result.timeline = await _generate_timeline(
        result.transcript,
        result.segments,
        result.visual_events,  # pass raw events
        result.duration_sec,
    )

    # ── Metadata ──────────────────────────────────────────────────────────
    result.analysis_time_ms = int((time.time() - start_time) * 1000)
    logger.info("[VIDEO] Analysis complete: %dms, %d frames, %d events",
                result.analysis_time_ms, result.frames_analyzed,
                len(result.visual_events))

    return result


# ── Convenience Functions ────────────────────────────────────────────────


async def analyze_video_meeting(
    video_path: str,
    engine: Optional[str] = None,
) -> VideoIntelligenceResult:
    """Analyze a meeting recording video."""
    return await analyze_video(
        video_path,
        engine=engine or "gemini",
        max_frames=30,
        frame_interval_sec=15.0,
    )


async def analyze_video_training(
    video_path: str,
    engine: Optional[str] = None,
) -> VideoIntelligenceResult:
    """Analyze a training video."""
    return await analyze_video(
        video_path,
        engine=engine or "hybrid",
        max_frames=40,
        frame_interval_sec=10.0,
    )


async def analyze_video_demo(
    video_path: str,
    engine: Optional[str] = None,
) -> VideoIntelligenceResult:
    """Analyze a system demo video."""
    return await analyze_video(
        video_path,
        engine=engine or "faster_whisper",
        max_frames=50,
        frame_interval_sec=5.0,
    )


# ── Lightweight Analysis (for ingestion pipeline) ─────────────────────────


async def analyze_video_light(
    video_path: str,
    mime_type: Optional[str] = None,
) -> dict[str, Any]:
    """Lightweight video analysis for the ingestion pipeline.

    Extracts video metadata via ffprobe only — no transcription or frame
    analysis (ingestion handles transcription separately via
    process_audio_for_rag()). Much faster than the full analyze_video().

    Returns a dict with key metadata:
      filename, duration_sec, width, height, fps, codec, video_type
    """
    info = _get_video_info(video_path)
    return {
        "filename": Path(video_path).name,
        "duration_sec": info.get("duration_sec", 0.0),
        "width": info.get("width", 0),
        "height": info.get("height", 0),
        "fps": info.get("fps", 0.0),
        "codec": info.get("codec", ""),
        "video_type": VideoType.RECORDING.value,
        "transcript": "",
        "segments": [],
        "transcription_engine": "",
        "transcription_confidence": 0.0,
        "analysis_time_ms": 0,
    }
