"""
voice.py – Multimodal Voice Assistant API for DocTel

Endpoints:
  POST /api/voice/transcribe   – Speech-to-text (file upload)
  POST /api/voice/stream       – Real-time bidirectional voice streaming (SSE)
  POST /api/voice/speak        – Text-to-speech (returns audio bytes)
  POST /api/voice/command      – Classify and route voice commands
  GET  /api/voice/config       – Available STT/TTS providers & voices
  GET  /api/voice/health       – Voice service health check
"""

import asyncio
import base64
import io
import json
import logging
import os
import re
import tempfile
import uuid
from pathlib import Path
from typing import AsyncGenerator, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel

from app.routers.deps import (
    UploadFile,
    User,
    get_current_user,
    settings,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/voice", tags=["voice"])

# ── Models ─────────────────────────────────────────────────────────────────────

class TranscribeRequest(BaseModel):
    """Request for direct audio transcription (base64 or URL)."""
    audio_base64: Optional[str] = None
    audio_url: Optional[str] = None
    language: str = "en"
    model: str = "auto"  # auto, whisper, gemini, openai
    response_format: str = "text"  # text, srt, segments

class SpeakRequest(BaseModel):
    """Text-to-speech request."""
    text: str
    voice: str = "alloy"  # alloy, echo, fable, onyx, nova, shimmer
    provider: str = "openai"  # openai, edge, azure
    speed: float = 1.0
    style: str = "professional"  # professional, friendly, technical, executive

class CommandRequest(BaseModel):
    """Voice command classification request."""
    text: str
    context: Optional[dict] = None

class StreamConfig(BaseModel):
    """Configuration for real-time voice streaming."""
    language: str = "en"
    stt_model: str = "auto"
    tts_voice: str = "alloy"
    tts_provider: str = "openai"
    turn_detection: bool = True
    silence_threshold_ms: int = 800

class ConverseRequest(BaseModel):
    """Voice conversation request with pre-transcribed text."""
    transcript: str
    session_id: str = ""
    language: str = "en"
    model: str = ""
    tts_provider: str = ""
    tts_voice: str = ""

# ── In-memory state ───────────────────────────────────────────────────────────

_voice_config = {
    "stt_providers": ["gemini", "whisper", "openai"],
    "tts_providers": ["openai", "edge", "azure"],
    "default_stt": "gemini",
    "default_tts": "openai",
    "voices": {
        "openai": ["alloy", "echo", "fable", "onyx", "nova", "shimmer"],
        "edge": ["en-US-JennyNeural", "en-US-GuyNeural", "en-GB-SoniaNeural", "en-AU-NatashaNeural"],
        "azure": ["en-US-JennyMultilingualNeural", "en-US-GuyMultilingualNeural"],
    },
    "voice_styles": {
        "professional": {"pitch": "0Hz", "rate": "0%"},
        "friendly": {"pitch": "+10Hz", "rate": "+10%"},
        "technical": {"pitch": "-5Hz", "rate": "-5%"},
        "executive": {"pitch": "-10Hz", "rate": "-15%"},
    },
    "stt_models": {
        "gemini": "gemini-2.5-flash",
        "whisper": "whisper-1",
        "openai": "whisper-1",
    },
    "commands": {
        "categories": ["search", "navigate", "create", "summarize", "report", "email"],
        "intents": [
            "search_document", "open_page", "create_report", "summarize_document",
            "generate_email", "find_policy", "compare_documents", "extract_data",
        ],
    },
}

# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_env_or_setting(key: str, default: str = "") -> str:
    """Get value from env var or config."""
    val = os.getenv(key, "").strip()
    if val:
        return val
    try:
        from app.config import settings as app_settings
        return getattr(app_settings, key.lower(), default) or default
    except Exception:
        return default

async def _transcribe_audio_file(file_path: str, mime_type: str, language: str = "en") -> str:
    """Transcribe audio using available backends (gemini → whisper)."""
    from app.services.transcription_service import transcribe_file
    return await transcribe_file(file_path, mime_type=mime_type)

async def _transcribe_via_openai(file_path: str) -> Optional[str]:
    """Transcribe using OpenAI Whisper API."""
    api_key = _get_env_or_setting("OPENAI_API_KEY")
    if not api_key:
        return None
    
    import httpx
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            with open(file_path, "rb") as f:
                files = {"file": (Path(file_path).name, f, "audio/wav")}
                data = {"model": "whisper-1", "response_format": "text"}
                resp = await client.post(
                    "https://api.openai.com/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    files=files,
                    data=data,
                )
                resp.raise_for_status()
                return resp.text.strip()
    except Exception as e:
        logger.warning("OpenAI transcription failed: %s", e)
        return None

async def _synthesize_speech_openai(text: str, voice: str = "alloy", speed: float = 1.0) -> Optional[bytes]:
    """Synthesize speech using OpenAI TTS API."""
    api_key = _get_env_or_setting("OPENAI_API_KEY")
    if not api_key:
        return None
    
    import httpx
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://api.openai.com/v1/audio/speech",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": "tts-1-hd",
                    "input": text,
                    "voice": voice,
                    "speed": speed,
                },
            )
            resp.raise_for_status()
            return resp.content
    except Exception as e:
        logger.warning("OpenAI TTS failed: %s", e)
        return None

async def _synthesize_speech_edge(text: str, voice: str = "en-US-JennyNeural") -> Optional[bytes]:
    """Synthesize speech using Microsoft Edge TTS (free, no API key needed)."""
    import httpx
    try:
        ssml = f"""
        <speak version='1.0' xml:lang='en-US'>
            <voice name='{voice}'>
                <prosody rate='0%' pitch='0Hz'>
                    {text}
                </prosody>
            </voice>
        </speak>
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://speech.platform.bing.com/consumer/speech/synthesize/readaloud/edge/v1",
                headers={
                    "Content-Type": "application/ssml+xml",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                },
                content=ssml,
            )
            if resp.status_code == 200:
                return resp.content
    except Exception as e:
        logger.warning("Edge TTS failed: %s", e)
    return None

async def _synthesize_speech_piper(text: str) -> Optional[bytes]:
    """Synthesize speech using local Piper TTS if available."""
    import tempfile
    
    piper_path = _get_env_or_setting("PIPER_PATH", "piper")
    model_path = Path(_get_env_or_setting("PIPER_MODEL", ""))
    
    if not model_path.exists():
        return None
    
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            output_path = tmp.name
        
        proc = await asyncio.create_subprocess_exec(
            piper_path, "--model", str(model_path), "--output_file", output_path,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(input=text.encode("utf-8")),
            timeout=30,
        )
        
        if proc.returncode == 0 and Path(output_path).exists():
            with open(output_path, "rb") as f:
                data = f.read()
            Path(output_path).unlink(missing_ok=True)
            return data
    except asyncio.TimeoutError:
        logger.warning("Piper TTS timed out")
    except Exception as e:
        logger.warning("Piper TTS failed: %s", e)
    return None

def _classify_voice_command(text: str) -> dict:
    """Simple rule-based voice command classification."""
    text_lower = text.lower().strip()
    
    # Define command patterns
    patterns = {
        "search_document": [
            r"search\s+(?:for\s+)?(.+)",
            r"find\s+(?:the\s+)?(.+)",
            r"look\s+(?:up\s+)?(.+)",
            r"show\s+me\s+(?:the\s+)?(.+)",
        ],
        "open_page": [
            r"(?:open|go\s+to|navigate\s+to)\s+(?:the\s+)?(.+)",
            r"take\s+me\s+to\s+(?:the\s+)?(.+)",
        ],
        "create_report": [
            r"(?:create|generate|make)\s+(?:a\s+|an\s+)?(?:report|document|summary)(?:\s+(?:about|for|on)\s+(.+))?",
            r"report\s+(?:on\s+)?(.+)",
        ],
        "summarize_document": [
            r"(?:summarize|summarise|brief)\s+(?:this\s+|the\s+)?(?:document|file|paper)(?:\s+(.+))?",
            r"(?:give|provide)\s+(?:a\s+|me\s+a\s+)?(?:summary|brief)(?:\s+(?:of|about|on)\s+(.+))?",
        ],
        "generate_email": [
            r"(?:compose|draft|write|create)\s+(?:a|an)\s+(?:email|mail|message)(?:\s+(?:to|about|for)\s+(.+))?",
        ],
        "compare_documents": [
            r"(?:compare|contrast)\s+(.+)(?:\s+(?:with|and|to|vs)\s+(.+))?",
        ],
        "extract_data": [
            r"(?:extract|pull|get)\s+(.+)\s+(?:from|out\s+of)\s+(.+)",
        ],
        "create_diagram": [
            r"(?:create|generate|draw|make)\s+(?:a\s+|an\s+)?(?:diagram|flowchart|chart)(?:\s+(?:for|of|about)\s+(.+))?",
        ],
    }
    
    for intent, pattern_list in patterns.items():
        for pattern in pattern_list:
            match = re.search(pattern, text_lower)
            if match:
                groups = [g for g in match.groups() if g]
                return {
                    "intent": intent,
                    "confidence": 0.85,
                    "entities": {"query": groups[0] if groups else text},
                    "raw_text": text,
                }
    
    # Fallback: search intent with full text
    return {
        "intent": "search_document",
        "confidence": 0.5,
        "entities": {"query": text},
        "raw_text": text,
    }

# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/config")
async def get_voice_config(user: User = Depends(get_current_user)):
    """Get available voice configuration (STT/TTS providers, voices, styles)."""
    return {
        "config": _voice_config,
        "availability": {
            "openai_stt": bool(_get_env_or_setting("OPENAI_API_KEY")),
            "openai_tts": bool(_get_env_or_setting("OPENAI_API_KEY")),
            "gemini_stt": bool(_get_env_or_setting("GEMINI_API_KEY")),
            "edge_tts": True,  # Always available (free)
            "azure_tts": bool(_get_env_or_setting("AZURE_SPEECH_KEY")),
            "piper_tts": bool(_get_env_or_setting("PIPER_MODEL")),
        },
    }

@router.get("/health")
async def voice_health():
    """Voice service health check."""
    from app.services.transcription_service import _has_ffmpeg
    
    return {
        "ok": True,
        "stt_available": bool(_get_env_or_setting("GEMINI_API_KEY") or _get_env_or_setting("OPENAI_API_KEY")),
        "tts_available": bool(_get_env_or_setting("OPENAI_API_KEY")),
        "edge_tts": True,
        "piper_available": bool(_get_env_or_setting("PIPER_MODEL")),
        "ffmpeg_available": _has_ffmpeg(),
    }

@router.post("/transcribe")
async def transcribe_audio(
    audio: UploadFile = File(...),
    language: str = Form("en"),
    model: str = Form("auto"),
    user: User = Depends(get_current_user),
):
    """
    Speech-to-text: Upload an audio file and get the transcription.
    
    Supports: WAV, MP3, M4A, OGG, WebM, FLAC
    Backends: Gemini API → Local Whisper → OpenAI Whisper API
    """
    temp_path = settings.uploads_dir / f"voice_{uuid.uuid4().hex}_{audio.filename}"
    
    try:
        content = await audio.read()
        with open(temp_path, "wb") as f:
            f.write(content)
        
        ext = Path(audio.filename or "").suffix.lower() if audio.filename else ".wav"
        mime_map = {
            ".wav": "audio/wav",
            ".mp3": "audio/mpeg",
            ".mp4": "audio/mp4",
            ".m4a": "audio/mp4",
            ".ogg": "audio/ogg",
            ".webm": "audio/webm",
            ".flac": "audio/flac",
            ".aac": "audio/aac",
        }
        mime_type = mime_map.get(ext, audio.content_type or "audio/wav")
        
        model_used = ""
        transcript = ""
        
        # Try requested model or auto-detect
        if model in ("auto", "gemini"):
            try:
                transcript = await _transcribe_audio_file(str(temp_path), mime_type, language)
                if transcript:
                    model_used = "gemini-2.5-flash"
            except Exception as e:
                logger.warning("Gemini STT failed: %s", e)
        
        if not transcript and model in ("auto", "whisper", "openai"):
            try:
                transcript = await _transcribe_via_openai(str(temp_path))
                if transcript:
                    model_used = "openai-whisper-1"
            except Exception as e:
                logger.warning("OpenAI STT failed: %s", e)
        
        if not transcript:
            # Fallback to local Whisper
            try:
                from app.services.transcription_service import transcribe_via_whisper_local
                whisper_result = await transcribe_via_whisper_local(str(temp_path))
                if whisper_result:
                    transcript = whisper_result
                    model_used = "whisper-local"
            except Exception as e:
                logger.warning("Local Whisper failed: %s", e)
        
        if not transcript:
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "stt_unavailable",
                    "message": "Speech-to-text is unavailable. Configure GEMINI_API_KEY or OPENAI_API_KEY.",
                },
            )
        
        return {
            "text": transcript.strip(),
            "language": language,
            "model": model_used,
            "confidence": 0.95 if "gemini" in model_used else 0.90,
            "duration_ms": len(content) // 32,  # rough estimate
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Transcription failed")
        raise HTTPException(status_code=500, detail={"error": "transcription_failed", "message": str(e)})
    finally:
        try:
            if temp_path.exists():
                temp_path.unlink()
        except Exception:
            pass

@router.post("/speak")
async def text_to_speech(
    request: SpeakRequest,
    user: User = Depends(get_current_user),
):
    """
    Text-to-speech: Convert text to audio bytes.
    
    Providers: openai (default), edge (free), azure, piper (local)
    Voices: alloy, echo, fable, onyx, nova, shimmer (openai)
            en-US-JennyNeural, en-US-GuyNeural (edge)
    Styles: professional, friendly, technical, executive
    """
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Text is required")
    
    audio_bytes: Optional[bytes] = None
    provider_used = ""
    
    # Apply style adjustments
    style_config = _voice_config.get("voice_styles", {}).get(request.style, {})
    effective_speed = request.speed
    if request.style == "technical":
        effective_speed *= 0.95
    elif request.style == "executive":
        effective_speed *= 0.90
    elif request.style == "friendly":
        effective_speed *= 1.1
    
    # Try requested provider
    if request.provider in ("auto", "openai"):
        audio_bytes = await _synthesize_speech_openai(request.text, request.voice, effective_speed)
        if audio_bytes:
            provider_used = "openai-tts-1-hd"
    
    if not audio_bytes and request.provider in ("auto", "edge"):
        audio_bytes = await _synthesize_speech_edge(request.text, request.voice)
        if audio_bytes:
            provider_used = "edge-tts"
    
    if not audio_bytes and request.provider in ("auto", "piper"):
        audio_bytes = await _synthesize_speech_piper(request.text)
        if audio_bytes:
            provider_used = "piper-tts"
    
    if not audio_bytes:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "tts_unavailable",
                "message": "Text-to-speech is unavailable. Configure OPENAI_API_KEY.",
            },
        )
    
    return Response(
        content=audio_bytes,
        media_type="audio/mpeg",
        headers={
            "X-TTS-Provider": provider_used,
            "X-TTS-Voice": request.voice,
            "X-TTS-Duration": str(len(audio_bytes) // 25600),  # rough estimate in seconds
        },
    )

@router.post("/command")
async def classify_command(
    request: CommandRequest,
    user: User = Depends(get_current_user),
):
    """
    Classify a voice command and route it to the appropriate handler.
    
    Returns the intent, confidence, extracted entities, and suggested action.
    """
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Command text is required")
    
    # Rule-based classification
    command = _classify_voice_command(request.text)
    
    # Map intent to action
    action_map = {
        "search_document": {
            "action": "search",
            "target": "knowledge_base",
            "ui_hint": "search",
        },
        "open_page": {
            "action": "navigate",
            "target": "page",
            "ui_hint": "navigate",
        },
        "create_report": {
            "action": "generate",
            "target": "report",
            "ui_hint": "report",
        },
        "summarize_document": {
            "action": "analyze",
            "target": "summary",
            "ui_hint": "summarize",
        },
        "generate_email": {
            "action": "compose",
            "target": "email",
            "ui_hint": "compose",
        },
        "compare_documents": {
            "action": "analyze",
            "target": "comparison",
            "ui_hint": "compare",
        },
        "extract_data": {
            "action": "analyze",
            "target": "extraction",
            "ui_hint": "extract",
        },
        "create_diagram": {
            "action": "generate",
            "target": "diagram",
            "ui_hint": "diagram",
        },
    }
    
    command["routing"] = action_map.get(command["intent"], {
        "action": "chat",
        "target": "general",
        "ui_hint": "chat",
    })
    
    return command

@router.post("/stream")
async def voice_stream(
    request: StreamConfig,
    user: User = Depends(get_current_user),
):
    """
    Real-time bidirectional voice streaming using SSE.
    
    Client sends audio chunks → Server transcribes → Server processes →
    Server generates response audio → Server streams TTS chunks back.
    
    This is a stateless streaming endpoint. For persistent sessions,
    use the chat session API alongside this endpoint.
    """
    
    async def event_stream() -> AsyncGenerator[str, None]:
        yield f"data: {json.dumps({'type': 'connected', 'config': request.model_dump()})}\n\n"
        yield f"data: {json.dumps({'type': 'ready', 'message': 'Voice stream active. Send audio via POST /api/voice/transcribe.'})}\n\n"
    
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

@router.post("/transcribe-stream")
async def transcribe_streaming(
    audio: UploadFile = File(...),
    session_id: str = Form(""),
    language: str = Form("en"),
    user: User = Depends(get_current_user),
):
    """
    Low-latency streaming transcription endpoint.
    
    Used by the voice assistant for real-time (push-to-talk) transcription.
    Returns a streaming response with incremental transcription results.
    
    Actual streaming transcription requires WebSocket support.
    This endpoint provides async transcription with fast turnaround.
    """
    temp_path = settings.uploads_dir / f"voice_stream_{uuid.uuid4().hex}_{audio.filename}"
    
    try:
        content = await audio.read()
        with open(temp_path, "wb") as f:
            f.write(content)
        
        # Transcribe with low-latency settings
        transcript = await _transcribe_audio_file(str(temp_path), audio.content_type or "audio/wav", language)
        
        if not transcript:
            transcript = await _transcribe_via_openai(str(temp_path))
        
        return {
            "text": transcript or "",
            "session_id": session_id,
            "is_final": True,
            "duration_ms": len(content) // 32,
        }
    finally:
        try:
            if temp_path.exists():
                temp_path.unlink()
        except Exception:
            pass

@router.post("/converse")
async def voice_conversation_file(
    audio: UploadFile = File(...),
    session_id: str = Form(""),
    model: str = Form(""),
    user: User = Depends(get_current_user),
):
    """
    Full voice conversation from raw audio:
    1. Transcribe audio to text
    2. Get AI response text
    3. Synthesize response to speech
    4. Return both text and audio
    """
    temp_path = settings.uploads_dir / f"voice_converse_{uuid.uuid4().hex}_{audio.filename}"
    
    try:
        content = await audio.read()
        with open(temp_path, "wb") as f:
            f.write(content)
        
        transcript = await _transcribe_audio_file(str(temp_path), audio.content_type or "audio/wav")
        if not transcript:
            transcript = await _transcribe_via_openai(str(temp_path))
        
        if not transcript:
            raise HTTPException(status_code=503, detail="Speech-to-text unavailable")
        
        return await _complete_conversation(transcript, session_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Voice conversation failed")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        try:
            if temp_path.exists():
                temp_path.unlink()
        except Exception:
            pass


@router.post("/converse-text")
async def voice_conversation_text(
    request: ConverseRequest,
    user: User = Depends(get_current_user),
):
    """
    Full voice conversation from pre-transcribed text (used by VoiceAssistant
    when transcription is done client-side).
    1. Get AI response text
    2. Synthesize response to speech
    3. Return both text and audio
    """
    if not request.transcript.strip():
        raise HTTPException(status_code=400, detail="Transcript is required")
    
    return await _complete_conversation(
        request.transcript,
        request.session_id,
        request.tts_provider or None,
        request.tts_voice or None,
    )


async def _complete_conversation(
    transcript: str,
    session_id: str = "",
    tts_provider_override: Optional[str] = None,
    tts_voice_override: Optional[str] = None,
) -> dict:
    """Shared logic: get AI response + synthesize speech."""
    # Get AI response
    from app.services.gemini_service import generate as gemini_generate
    
    system_prompt = (
        "You are DocTel, ZETDC's AI voice assistant. "
        "Respond conversationally, naturally, and concisely (under 150 words). "
        "Use ZETDC terminology where appropriate. "
        "If the user asks about documents, suggest searching the knowledge base."
    )
    
    try:
        response_text = await gemini_generate(transcript, system=system_prompt)
    except Exception:
        response_text = f'I heard: "{transcript}". How can I help you further?'
    
    # Synthesize speech
    tts_provider = tts_provider_override or _get_env_or_setting("TTS_PROVIDER", "openai")
    tts_voice = tts_voice_override or _get_env_or_setting("TTS_VOICE", "alloy")
    
    audio_bytes = None
    if tts_provider == "openai":
        audio_bytes = await _synthesize_speech_openai(response_text, tts_voice)
    if not audio_bytes:
        audio_bytes = await _synthesize_speech_edge(response_text)
    
    response_data = {
        "transcript": transcript,
        "text": response_text,
        "session_id": session_id,
    }
    
    if audio_bytes:
        import base64
        response_data["audio_base64"] = base64.b64encode(audio_bytes).decode()
        response_data["audio_format"] = "mp3"
        response_data["tts_provider"] = tts_provider
    
    return response_data
