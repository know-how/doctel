"""
transcription_router_service.py — DocTel Hybrid Audio Intelligence Router

Routes transcription requests to the best available engine:
  - Faster-Whisper (local, fast, private)
  - Gemini (cloud, Shona+English, high quality)
  - Hybrid (parallel, compare, pick best)

Architecture:

  transcribe_audio()
    ↓
  select_engine()   ← Checks config + availability
    ↓
  FASTER_WHISPER ──→ transcribe_via_faster_whisper()
  GEMINI        ──→ transcribe_via_gemini()
  HYBRID        ──→ transcribe_hybrid()  ← Run both in parallel, compare
    ↓
  TranscriptionResult (normalized output)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ── Enums ─────────────────────────────────────────────────────────────────


class TranscriptionEngine(str, Enum):
    """Available transcription engines."""
    FASTER_WHISPER = "faster_whisper"
    GEMINI = "gemini"
    HYBRID = "hybrid"


class EnginePriority(str, Enum):
    """How engines should be prioritized."""
    FASTER_WHISPER_FIRST = "faster_whisper_first"  # Default
    GEMINI_FIRST = "gemini_first"
    HYBRID_ONLY = "hybrid_only"


# ── Data Classes ──────────────────────────────────────────────────────────


@dataclass
class TranscriptionSegment:
    """A single timed segment from transcription."""
    start_sec: float = 0.0
    end_sec: float = 0.0
    text: str = ""
    confidence: float = 1.0
    speaker: Optional[str] = None
    language: str = "en"


@dataclass
class TranscriptionResult:
    """Normalized transcription result from any engine."""
    full_text: str = ""
    segments: list[TranscriptionSegment] = field(default_factory=list)
    language: str = "en"
    duration_sec: Optional[float] = None
    source_type: str = "audio"
    engine: str = "faster_whisper"
    engines_used: list[str] = field(default_factory=list)
    confidence: float = 0.0
    agreement_score: Optional[float] = None
    word_count: int = 0
    model_used: str = ""
    processing_time_ms: int = 0
    error: Optional[str] = None


# ── Configuration ─────────────────────────────────────────────────────────


class TranscriptionConfig:
    """Configuration for transcription engine selection.

    Priority:
      1. Explicit engine override in request
      2. Environment variable DOCTEL_TRANSCRIPTION_ENGINE
      3. Default: faster_whisper_first
    """

    def __init__(self):
        self.default_priority = os.getenv(
            "DOCTEL_TRANSCRIPTION_ENGINE", "faster_whisper_first"
        )
        # Faster-Whisper model: default large-v3, fallback medium
        self.faster_whisper_model = os.getenv(
            "DOCTEL_WHISPER_MODEL", "large-v3"
        )
        self.faster_whisper_device = os.getenv(
            "DOCTEL_WHISPER_DEVICE", "auto"
        )  # auto | cpu | cuda
        self.faster_whisper_compute_type = os.getenv(
            "DOCTEL_WHISPER_COMPUTE", "default"
        )  # default | float16 | int8_float16
        # Gemini config (read from gemini_service)
        self.gemini_timeout = int(os.getenv("DOCTEL_GEMINI_TIMEOUT", "120"))
        # Hybrid mode
        self.hybrid_min_agreement = float(
            os.getenv("DOCTEL_HYBRID_MIN_AGREEMENT", "0.7")
        )
        self.hybrid_timeout = int(os.getenv("DOCTEL_HYBRID_TIMEOUT", "180"))


# ── Engine Check ──────────────────────────────────────────────────────────


def check_faster_whisper_available() -> tuple[bool, str]:
    """Check if faster-whisper is installable/importable."""
    try:
        import faster_whisper as _fw
        # Quick version check
        version = getattr(_fw, "__version__", "unknown")
        return True, f"faster-whisper {version}"
    except ImportError:
        return False, "faster-whisper not installed"
    except Exception as e:
        return False, str(e)


def check_gemini_available() -> tuple[bool, str]:
    """Check if Gemini API is configured."""
    try:
        from app.services.gemini_service import is_configured, get_display_name
        if is_configured():
            return True, get_display_name()
        return False, "Gemini not configured"
    except Exception as e:
        return False, str(e)


def get_available_engines() -> dict[str, dict]:
    """Return availability status for all engines."""
    fw_ok, fw_msg = check_faster_whisper_available()
    gm_ok, gm_msg = check_gemini_available()
    return {
        "faster_whisper": {"available": fw_ok, "detail": fw_msg},
        "gemini": {"available": gm_ok, "detail": gm_msg},
        "hybrid": {"available": fw_ok and gm_ok, "detail": "Requires both engines"},
    }


# ── Engine Implementations ────────────────────────────────────────────────


async def _transcribe_faster_whisper(
    audio_path: str,
    config: TranscriptionConfig,
    language: Optional[str] = None,
) -> TranscriptionResult:
    """Transcribe using faster-whisper (CTranslate2-based)."""
    start = time.time()
    try:
        from faster_whisper import WhisperModel

        # Determine device and compute type
        device = config.faster_whisper_device
        if device == "auto":
            try:
                import torch
                device = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                device = "cpu"

        compute_type = config.faster_whisper_compute_type
        if compute_type == "default":
            compute_type = "float16" if device == "cuda" else "int8"

        model = WhisperModel(
            config.faster_whisper_model,
            device=device,
            compute_type=compute_type,
        )

        # Run transcription
        loop = asyncio.get_event_loop()

        def _run_whisper():
            segments, info = model.transcribe(
                audio_path,
                language=language or "en",
                beam_size=5,
                vad_filter=True,
                vad_parameters={"min_silence_duration_ms": 500},
            )
            result_segments = []
            for seg in segments:
                result_segments.append(TranscriptionSegment(
                    start_sec=seg.start,
                    end_sec=seg.end,
                    text=seg.text.strip(),
                    confidence=seg.avg_logprob if seg.avg_logprob else 1.0,
                    language=info.language if info else "en",
                ))
            return result_segments, info

        segs, info = await loop.run_in_executor(None, _run_whisper)
        full_text = " ".join(s.text for s in segs)

        elapsed_ms = int((time.time() - start) * 1000)

        # Cleanup GPU memory
        del model
        try:
            import gc
            gc.collect()
            if device == "cuda":
                import torch
                torch.cuda.empty_cache()
        except Exception:
            pass

        return TranscriptionResult(
            full_text=full_text,
            segments=segs,
            language=info.language if info else "en",
            source_type="audio",
            engine="faster_whisper",
            engines_used=["faster_whisper"],
            confidence=0.8,
            word_count=len(full_text.split()),
            model_used=f"faster-whisper/{config.faster_whisper_model}",
            processing_time_ms=elapsed_ms,
        )

    except Exception as e:
        elapsed_ms = int((time.time() - start) * 1000)
        logger.warning("[TRANSCRIBE:FW] Failed: %s", e)
        return TranscriptionResult(
            error=f"faster-whisper error: {e}",
            engine="faster_whisper",
            processing_time_ms=elapsed_ms,
        )


async def _transcribe_gemini(
    audio_path: str,
    mime_type: Optional[str] = None,
    timeout: int = 120,
) -> TranscriptionResult:
    """Transcribe using Gemini API.

    Reuses the existing transcribe_via_gemini function, but wraps
    the result in the standardized TranscriptionResult format.
    """
    start = time.time()
    try:
        from app.services.transcription_service import (
            transcribe_via_gemini,
            transcribe_file_structured,
        )

        # Use the structured transcription which returns full metadata
        result = await transcribe_file_structured(audio_path, mime_type)
        elapsed_ms = int((time.time() - start) * 1000)

        if result.full_text:
            # Convert existing segments to our format
            segments = [
                TranscriptionSegment(
                    start_sec=s.start_sec,
                    end_sec=s.end_sec,
                    text=s.text,
                    confidence=getattr(s, 'confidence', 0.9),
                    speaker=getattr(s, 'speaker', None),
                    language=result.language,
                )
                for s in result.segments
            ] if result.segments else [
                TranscriptionSegment(
                    text=result.full_text,
                    confidence=0.9,
                    language=result.language,
                )
            ]

            return TranscriptionResult(
                full_text=result.full_text,
                segments=segments,
                language=result.language,
                duration_sec=result.duration_sec,
                source_type=result.source_type,
                engine="gemini",
                engines_used=["gemini"],
                confidence=0.9,
                word_count=result.word_count,
                model_used=result.model_used or "gemini",
                processing_time_ms=elapsed_ms,
            )

        return TranscriptionResult(
            error="Gemini returned empty transcript",
            engine="gemini",
            processing_time_ms=elapsed_ms,
        )

    except Exception as e:
        elapsed_ms = int((time.time() - start) * 1000)
        logger.warning("[TRANSCRIBE:GEMINI] Failed: %s", e)
        return TranscriptionResult(
            error=f"Gemini error: {e}",
            engine="gemini",
            processing_time_ms=elapsed_ms,
        )


async def _transcribe_hybrid(
    audio_path: str,
    config: TranscriptionConfig,
    mime_type: Optional[str] = None,
    language: Optional[str] = None,
) -> TranscriptionResult:
    """Run Faster-Whisper and Gemini in parallel, compare results.

    Strategy:
    1. Launch both engines concurrently
    2. Wait for both to complete (with timeout)
    3. Calculate agreement score between transcripts
    4. Select best result based on confidence + agreement
    5. Return with both engines noted
    """
    start = time.time()

    async def run_fw():
        return await _transcribe_faster_whisper(audio_path, config, language)

    async def run_gemini():
        return await _transcribe_gemini(audio_path, mime_type, config.gemini_timeout)

    # Run both in parallel
    fw_task = asyncio.create_task(run_fw())
    gm_task = asyncio.create_task(run_gemini())

    try:
        fw_result, gm_result = await asyncio.wait_for(
            asyncio.gather(fw_task, gm_task, return_exceptions=True),
            timeout=config.hybrid_timeout,
        )
    except asyncio.TimeoutError:
        elapsed_ms = int((time.time() - start) * 1000)
        logger.warning("[TRANSCRIBE:HYBRID] Timed out after %ds", config.hybrid_timeout)
        # Try to get whichever finished first
        results = []
        for task in [fw_task, gm_task]:
            if task.done() and not task.exception():
                results.append(task.result())
        if results:
            best = max(results, key=lambda r: r.confidence if not r.error else 0)
            best.engines_used = ["faster_whisper", "gemini"]
            best.engine = "hybrid"
            best.processing_time_ms = elapsed_ms
            return best
        return TranscriptionResult(
            error="Hybrid transcription timed out",
            engine="hybrid",
            processing_time_ms=elapsed_ms,
        )

    # Handle exceptions from either engine
    if isinstance(fw_result, Exception):
        logger.warning("[TRANSCRIBE:HYBRID] Faster-Whisper failed: %s", fw_result)
        fw_result = TranscriptionResult(error=str(fw_result), engine="faster_whisper")
    if isinstance(gm_result, Exception):
        logger.warning("[TRANSCRIBE:HYBRID] Gemini failed: %s", gm_result)
        gm_result = TranscriptionResult(error=str(gm_result), engine="gemini")

    elapsed_ms = int((time.time() - start) * 1000)

    # Calculate agreement score between successful transcripts
    agreement = None
    if fw_result.full_text and gm_result.full_text:
        fw_words = set(fw_result.full_text.lower().split())
        gm_words = set(gm_result.full_text.lower().split())
        if fw_words and gm_words:
            overlap = len(fw_words & gm_words)
            total = len(fw_words | gm_words)
            agreement = overlap / total if total > 0 else 0.0

    # Select best result
    candidates = []
    if fw_result.full_text:
        candidates.append(("faster_whisper", fw_result, fw_result.confidence))
    if gm_result.full_text:
        candidates.append(("gemini", gm_result, gm_result.confidence))

    if not candidates:
        elapsed_ms = int((time.time() - start) * 1000)
        return TranscriptionResult(
            error="Both engines failed in hybrid mode",
            engine="hybrid",
            engines_used=["faster_whisper", "gemini"],
            processing_time_ms=elapsed_ms,
        )

    # Pick the one with higher confidence
    best_name, best_result, best_conf = max(candidates, key=lambda c: c[2])

    best_result.engine = "hybrid"
    best_result.engines_used = ["faster_whisper", "gemini"]
    best_result.agreement_score = round(agreement, 3) if agreement is not None else None
    best_result.confidence = round(
        best_conf * (0.7 + 0.3 * (agreement or 0)), 3
    )
    best_result.processing_time_ms = elapsed_ms

    logger.info(
        "[TRANSCRIBE:HYBRID] Complete — engine=%s confidence=%.2f agreement=%.2f time=%dms",
        best_name, best_result.confidence, agreement or 0, elapsed_ms,
    )

    return best_result


# ── Public API ────────────────────────────────────────────────────────────


async def transcribe_audio(
    audio_path: str,
    mime_type: Optional[str] = None,
    engine: Optional[str] = None,
    language: Optional[str] = None,
    config: Optional[TranscriptionConfig] = None,
) -> TranscriptionResult:
    """Transcribe an audio file using the best available engine.

    Parameters
    ----------
    audio_path : str
        Path to audio file.
    mime_type : str or None
        MIME type for Gemini API.
    engine : str or None
        Override engine selection: "faster_whisper", "gemini", "hybrid".
        If None, uses config default.
    language : str or None
        Language hint for transcription.
    config : TranscriptionConfig or None
        Configuration. Uses defaults if None.

    Returns
    -------
    TranscriptionResult
        Normalized transcription result.
    """
    if config is None:
        config = TranscriptionConfig()

    file_path = Path(audio_path)
    if not file_path.exists():
        return TranscriptionResult(error=f"File not found: {audio_path}")

    # Determine engine priority
    engine_str = engine or config.default_priority

    # Map priority strings to engine
    if engine_str in ("faster_whisper_first", TranscriptionEngine.FASTER_WHISPER.value):
        # Try faster-whisper first, fallback to Gemini
        fw_result = await _transcribe_faster_whisper(audio_path, config, language)
        if fw_result.full_text and not fw_result.error:
            return fw_result
        logger.info("[TRANSCRIBE] Faster-Whisper failed, falling back to Gemini")
        return await _transcribe_gemini(audio_path, mime_type, config.gemini_timeout)
    elif engine_str in ("gemini_first", TranscriptionEngine.GEMINI.value):
        return await _transcribe_gemini(audio_path, mime_type, config.gemini_timeout)
    elif engine_str in ("hybrid_only", TranscriptionEngine.HYBRID.value):
        return await _transcribe_hybrid(audio_path, config, mime_type, language)
    else:
        # Unknown engine — try faster-whisper, fallback Gemini
        fw_result = await _transcribe_faster_whisper(audio_path, config, language)
        if fw_result.full_text and not fw_result.error:
            return fw_result
        return await _transcribe_gemini(audio_path, mime_type, config.gemini_timeout)


async def transcribe_audio_hybrid(
    audio_path: str,
    mime_type: Optional[str] = None,
    language: Optional[str] = None,
) -> TranscriptionResult:
    """Convenience: transcribe using hybrid mode."""
    return await transcribe_audio(
        audio_path, mime_type=mime_type, engine="hybrid", language=language
    )


async def transcribe_audio_fast(
    audio_path: str,
    language: Optional[str] = None,
) -> TranscriptionResult:
    """Convenience: transcribe using faster-whisper only."""
    return await transcribe_audio(
        audio_path, engine="faster_whisper", language=language
    )


async def transcribe_audio_premium(
    audio_path: str,
    mime_type: Optional[str] = None,
    language: Optional[str] = None,
) -> TranscriptionResult:
    """Convenience: transcribe using Gemini only (best for Shona+English)."""
    return await transcribe_audio(
        audio_path, mime_type=mime_type, engine="gemini", language=language
    )


# ── Diagnostics ───────────────────────────────────────────────────────────


def diagnose_transcription_setup() -> dict[str, Any]:
    """Diagnose the transcription setup and return availability status."""
    engines = get_available_engines()
    config = TranscriptionConfig()
    return {
        "engines": engines,
        "default_priority": config.default_priority,
        "faster_whisper_model": config.faster_whisper_model,
        "hybrid_mode": engines.get("hybrid", {}).get("available", False),
        "hybrid_min_agreement": config.hybrid_min_agreement,
        "recommended": "hybrid" if engines.get("hybrid", {}).get("available")
                      else "faster_whisper" if engines.get("faster_whisper", {}).get("available")
                      else "gemini" if engines.get("gemini", {}).get("available")
                      else "none",
    }
