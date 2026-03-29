from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.config import get_settings
from app.dependencies import get_tts_client
from app.routers.auth import get_current_user

router = APIRouter(prefix="/api/voice", tags=["voice"])


class TTSRequest(BaseModel):
    text: str


@router.get("/capabilities")
async def voice_capabilities() -> dict[str, bool]:
    """Return which voice features are available based on current configuration."""
    settings = get_settings()
    return {"tts_available": settings.has_tts}


@router.post("/tts")
async def text_to_speech(
    body: TTSRequest,
    user=Depends(get_current_user),
) -> StreamingResponse:
    """Convert text to speech and stream back MP3 audio."""
    client = get_tts_client()
    if client is None:
        raise HTTPException(
            status_code=503, detail="TTS not configured: OPENAI_API_KEY is required"
        )

    settings = get_settings()
    text = body.text[:4096]

    response = await client.audio.speech.create(
        model=settings.TTS_MODEL,
        voice=settings.TTS_VOICE,
        input=text,
        response_format="mp3",
    )

    return StreamingResponse(
        response.iter_bytes(),
        media_type="audio/mpeg",
        headers={"Content-Disposition": "inline"},
    )
