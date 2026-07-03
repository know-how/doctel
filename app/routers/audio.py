"""Audio transcription endpoint."""

import json

from fastapi import APIRouter
from pathlib import Path

from app.routers.deps import (
    UploadFile,
    File,
    Form,
    Depends,
    HTTPException,
    JSONResponse,
    User,
    get_current_user,
    settings,
    uuid,
)

router = APIRouter(tags=["audio"])


@router.post("/api/audio/transcribe")
async def transcribe_audio(
    audio: UploadFile = File(...),
    language: str = Form("en"),
    user: User = Depends(get_current_user),
):
    from app.services.transcription_service import transcribe_file

    temp_path = settings.uploads_dir / f"audio_{uuid.uuid4().hex}_{audio.filename}"
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
        }
        mime_type = mime_map.get(ext, audio.content_type or "audio/wav")

        transcript = await transcribe_file(str(temp_path), mime_type=mime_type)

        if transcript:
            model_used = "gemini/whisper-local"
        else:
            return JSONResponse(
                status_code=503,
                content={
                    "error": "audio_transcription_unavailable",
                    "message": "Audio transcription failed. Ensure GEMINI_API_KEY is configured or Whisper model is available.",
                },
            )

        return {"text": transcript.strip(), "language": language, "model": model_used}
    except HTTPException:
        raise
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": "transcription_failed", "detail": str(e)},
        )
    finally:
        try:
            if temp_path.exists():
                temp_path.unlink()
        except Exception:
            pass
