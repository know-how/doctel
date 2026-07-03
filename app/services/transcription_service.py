"""
transcription_service.py – Transcribe audio and video files for ingestion.

Primary: Gemini API (cloud, Shona+English)
Fallback: Local Whisper via transformers (if GPU/CPU available)

Video files are handled by extracting audio via ffmpeg, then transcribing.
If ffmpeg is not available, video transcription falls back to Gemini vision
(frame-by-frame analysis).
"""
import asyncio
import base64
import json
import logging
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List

logger = logging.getLogger(__name__)


@dataclass
class TranscriptionSegment:
    """A single timed segment from an audio/video transcription."""
    start_sec: float
    end_sec: float
    text: str
    confidence: float = 1.0
    speaker: Optional[str] = None
    language: str = "en"


@dataclass
class TranscriptionResult:
    """Complete transcription result with segments and metadata."""
    full_text: str
    segments: List[TranscriptionSegment] = field(default_factory=list)
    language: str = "en"
    duration_sec: Optional[float] = None
    source_type: str = "audio"  # "audio" | "video" | "text"
    model_used: str = ""
    word_count: int = 0

AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".ogg", ".webm", ".flac", ".aac", ".wma"}
VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv", ".webm"}
AUDIO_MIME_MAP = {
    ".wav": "audio/wav",
    ".mp3": "audio/mpeg",
    ".mp4": "audio/mp4",
    ".m4a": "audio/mp4",
    ".ogg": "audio/ogg",
    ".webm": "audio/webm",
    ".flac": "audio/flac",
    ".aac": "audio/aac",
    ".wma": "audio/x-ms-wma",
}

_ZETDC_TRANSCRIPTION_PROMPT = (
    "Transcribe the following audio accurately. "
    "If the audio is in Shona, transcribe in Shona and also provide an English translation. "
    "If the audio is in English, transcribe in English. "
    "Preserve the exact words spoken. "
    "Context: This is a recording from ZETDC (Zimbabwe Electricity Transmission and Distribution Company). "
    "Use ZETDC terminology where applicable: transmission, distribution, substations, feeders, SCADA, HSE, ZERA, ZUMS."
)


def _has_ffmpeg() -> bool:
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True, text=True, timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


def _extract_audio_from_video(video_path: str, output_path: Optional[str] = None) -> Optional[str]:
    if not _has_ffmpeg():
        logger.warning("ffmpeg not available – cannot extract audio from video")
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
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode == 0 and Path(output_path).exists():
            return output_path
        logger.warning("ffmpeg audio extraction failed: %s", result.stderr[:200])
        return None
    except Exception as e:
        logger.warning("ffmpeg exception: %s", e)
        return None


async def transcribe_via_gemini(file_path: str, mime_type: Optional[str] = None) -> Optional[str]:
    from app.services.gemini_service import is_configured as gemini_ok
    if not gemini_ok():
        return None

    import httpx

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    with open(file_path, "rb") as f:
        audio_b64 = base64.standard_b64encode(f.read()).decode()

    ext = Path(file_path).suffix.lower()
    resolved_mime = mime_type or AUDIO_MIME_MAP.get(ext, "audio/wav")

    body = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": _ZETDC_TRANSCRIPTION_PROMPT},
                    {"inlineData": {"mimeType": resolved_mime, "data": audio_b64}},
                ],
            }
        ],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 4096},
    }

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(url, json=body)
            resp.raise_for_status()
            data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        logger.warning("Gemini transcription failed: %s", e)
        return None


async def transcribe_via_whisper_local(file_path: str) -> Optional[str]:
    try:
        import torch
        from transformers import WhisperForConditionalGeneration, WhisperProcessor

        device = "cuda" if torch.cuda.is_available() else "cpu"
        model_name = os.getenv("DOCTEL_WHISPER_MODEL", "openai/whisper-small")

        try:
            processor = WhisperProcessor.from_pretrained(model_name)
            model = WhisperForConditionalGeneration.from_pretrained(model_name).to(device)
        except Exception as e:
            logger.warning("Failed to load Whisper model '%s': %s. Trying whisper-tiny.", model_name, e)
            model_name = "openai/whisper-tiny"
            processor = WhisperProcessor.from_pretrained(model_name)
            model = WhisperForConditionalGeneration.from_pretrained(model_name).to(device)

        import librosa
        speech, sr = librosa.load(file_path, sr=16000)
        input_features = processor(speech, sampling_rate=16000, return_tensors="pt").input_features.to(device)

        predicted_ids = model.generate(input_features, language="en", task="transcribe")
        transcription = processor.batch_decode(predicted_ids, skip_special_tokens=True)[0]

        if torch.cuda.is_available():
            del model
            torch.cuda.empty_cache()

        return transcription.strip()
    except Exception as e:
        logger.warning("Local Whisper transcription failed: %s", e)
        return None


def _parse_timestamp(ts_str: str) -> float:
    """Parse SRT/VTT timestamp string to seconds."""
    try:
        ts_str = ts_str.strip().replace(",", ".")
        parts = ts_str.split(":")
        if len(parts) == 3:
            h, m, s = parts
            return int(h) * 3600 + int(m) * 60 + float(s)
        elif len(parts) == 2:
            m, s = parts
            return int(m) * 60 + float(s)
        return 0.0
    except Exception:
        return 0.0


def _parse_srt(srt_text: str) -> list[TranscriptionSegment]:
    """Parse SRT subtitle format into segments."""
    segments: list[TranscriptionSegment] = []
    blocks = re.split(r'\n\n+', srt_text.strip())
    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) < 3:
            continue
        # Look for a line with -->
        time_line = None
        text_start = None
        for idx, line in enumerate(lines):
            if '-->' in line:
                time_line = line
                text_start = idx + 1
                break
        if time_line is None:
            continue
        try:
            time_parts = time_line.split('-->')
            start = _parse_timestamp(time_parts[0])
            end = _parse_timestamp(time_parts[1])
        except Exception:
            continue
        text = ' '.join(lines[text_start:]).strip()
        if text:
            segments.append(TranscriptionSegment(
                start_sec=start,
                end_sec=end,
                text=text,
            ))
    return segments


async def transcribe_file(file_path: str, mime_type: Optional[str] = None) -> str:
    """
    Transcribe an audio or video file. Returns the full transcript text.

    Priority: Gemini API → Local Whisper → empty string
    For video: extracts audio via ffmpeg first, then transcribes.
    """
    result = await transcribe_file_structured(file_path, mime_type)
    return result.full_text


async def transcribe_file_structured(
    file_path: str,
    mime_type: Optional[str] = None,
) -> TranscriptionResult:
    """
    Transcribe an audio/video file and return a structured TranscriptionResult
    with per-segment timing, confidence, speaker labels, and source metadata.

    Priority: Gemini API → Local Whisper → empty TranscriptionResult
    For video: extracts audio via ffmpeg first.
    Gemini may return SRT-like segments; if so they are parsed into timed segments.
    Whisper fallback returns a plain string (no timings), placed into a single segment.
    """
    ext = Path(file_path).suffix.lower()
    audio_path = file_path
    temp_audio = None
    source_type = "video" if ext in VIDEO_EXTENSIONS else "audio"
    mime = mime_type or AUDIO_MIME_MAP.get(ext, "audio/wav")

    # Extract audio from video if needed
    if ext in VIDEO_EXTENSIONS:
        temp_audio = _extract_audio_from_video(file_path)
        if temp_audio:
            audio_path = temp_audio
            mime = "audio/wav"
        else:
            logger.warning("Cannot extract audio from video %s", file_path)

    # Get file size for duration estimate (rough)
    file_size = Path(file_path).stat().st_size if Path(file_path).exists() else 0

    # --- Try Gemini first (can return SRT-structured output) ---
    gemini_text = await transcribe_via_gemini(audio_path, mime)
    if gemini_text:
        # Try to parse as SRT (Gemini can be prompted to return SRT)
        segments = _parse_srt(gemini_text)
        if not segments:
            # Plain text — create one segment
            segs = gemini_text.strip().split('\n')
            segments = []
            for s in segs:
                s = s.strip()
                if s:
                    segments.append(TranscriptionSegment(
                        start_sec=0.0,
                        end_sec=0.0,
                        text=s,
                        confidence=0.9,
                    ))

        full_text = ' '.join(s.text for s in segments)
        word_count = len(full_text.split())
        if temp_audio:
            try:
                Path(temp_audio).unlink()
            except Exception:
                pass
        return TranscriptionResult(
            full_text=full_text,
            segments=segments,
            language="en",
            duration_sec=None,
            source_type=source_type,
            model_used="gemini-2.5-flash",
            word_count=word_count,
        )

    # --- Fallback to local Whisper ---
    whisper_text = await transcribe_via_whisper_local(audio_path)
    if temp_audio:
        try:
            Path(temp_audio).unlink()
        except Exception:
            pass

    if whisper_text:
        word_count = len(whisper_text.split())
        return TranscriptionResult(
            full_text=whisper_text,
            segments=[TranscriptionSegment(
                start_sec=0.0,
                end_sec=0.0,
                text=whisper_text,
                confidence=0.8,
            )],
            language="en",
            duration_sec=None,
            source_type=source_type,
            model_used=f"whisper-local",
            word_count=word_count,
        )

    # --- Empty result ---
    if temp_audio:
        try:
            Path(temp_audio).unlink()
        except Exception:
            pass
    return TranscriptionResult(
        full_text="",
        segments=[],
        language="en",
        duration_sec=None,
        source_type=source_type,
        model_used="",
        word_count=0,
    )


async def process_audio_for_rag(
    file_path: str,
    mime_type: Optional[str] = None,
    max_segment_duration_sec: float = 30.0,
) -> dict:
    """
    Transcribe audio and produce RAG-ready structured output:
    - Full transcript text
    - Timed segments (each ≤ max_segment_duration_sec) suitable for chunking
    - Source metadata (duration, language, source_type)
    - Suggested chunk boundaries aligned to sentence/segment boundaries

    Returns a dict with keys:
      full_text, segments, language, duration_sec, source_type,
      model_used, word_count, rag_chunks

    Each rag_chunk dict: {"text": str, "start_sec": float, "end_sec": float,
                         "speaker": Optional[str], "chunk_index": int}
    """
    import math

    result = await transcribe_file_structured(file_path, mime_type)

    # Build RAG chunks aligned to natural segment boundaries
    rag_chunks: list[dict] = []
    chunk_idx = 0
    buffer_text = ""
    buffer_start = 0.0
    buffer_end = 0.0
    current_speaker = None

    for seg in result.segments:
        # Start buffer at first segment
        if not buffer_text:
            buffer_text = seg.text
            buffer_start = seg.start_sec
            buffer_end = seg.end_sec
            current_speaker = seg.speaker
            continue

        # Check if adding this segment would exceed duration or change speaker
        duration_with_seg = seg.end_sec - buffer_start
        speaker_changed = (
            current_speaker is not None
            and seg.speaker is not None
            and seg.speaker != current_speaker
        )

        if duration_with_seg > max_segment_duration_sec or speaker_changed:
            # Flush current buffer as a chunk
            rag_chunks.append({
                "text": buffer_text.strip(),
                "start_sec": buffer_start,
                "end_sec": buffer_end,
                "speaker": current_speaker,
                "chunk_index": chunk_idx,
            })
            chunk_idx += 1
            buffer_text = seg.text
            buffer_start = seg.start_sec
            buffer_end = seg.end_sec
            current_speaker = seg.speaker
        else:
            # Append to buffer
            if buffer_text:
                buffer_text += " " + seg.text
            else:
                buffer_text = seg.text
            buffer_end = seg.end_sec

    # Flush final buffer
    if buffer_text.strip():
        rag_chunks.append({
            "text": buffer_text.strip(),
            "start_sec": buffer_start,
            "end_sec": buffer_end,
            "speaker": current_speaker,
            "chunk_index": chunk_idx,
        })

    return {
        "full_text": result.full_text,
        "segments": [asdict(s) for s in result.segments],
        "language": result.language,
        "duration_sec": result.duration_sec,
        "source_type": result.source_type,
        "model_used": result.model_used,
        "word_count": result.word_count,
        "rag_chunks": rag_chunks,
    }


async def transcribe_and_save_training_sample(
    file_path: str,
    output_dir: Optional[Path] = None,
) -> dict:
    """
    Transcribe an audio/video file and save the transcript as a training sample.
    Returns {"transcript": str, "training_file": str, "chars": int}
    """
    from app.config import settings

    if output_dir is None:
        output_dir = Path(settings.base_dir) / "training" / "transcripts"
    output_dir.mkdir(parents=True, exist_ok=True)

    transcript = await transcribe_file(file_path)

    if not transcript:
        return {"transcript": "", "training_file": "", "chars": 0}

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = Path(file_path).stem
    outfile = output_dir / f"transcript_{filename}_{ts}.jsonl"

    record = {
        "instruction": "Transcribe the following ZETDC audio recording. Use ZETDC terminology and provide both Shona and English where applicable.",
        "input": "",
        "output": transcript,
        "source_file": Path(file_path).name,
        "transcribed_at": datetime.now(timezone.utc).isoformat(),
        "type": "audio_transcription",
    }

    with open(outfile, "w", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return {
        "transcript": transcript,
        "training_file": str(outfile),
        "chars": len(transcript),
    }
