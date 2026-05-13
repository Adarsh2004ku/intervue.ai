import base64
import httpx
from backend.core.config import settings
from backend.core.logging import get_logger


logger = get_logger("elevenlabs_tts")


def _tts_url(voice_id: str) -> str:
    return f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"


async def synthesize_interviewer_speech(
    text: str,
    voice_id: str | None = None,
) -> dict:
    clean_text = text.strip()
    if not clean_text:
        return {
            "success": False,
            "error": "No text provided",
        }

    if not settings.elevenlabs_api_key:
        return {
            "success": False,
            "error": "ELEVENLABS_API_KEY is not configured",
        }

    selected_voice_id = voice_id or settings.elevenlabs_voice_id

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                _tts_url(selected_voice_id),
                params={
                    "output_format": settings.elevenlabs_output_format,
                },
                headers={
                    "xi-api-key": settings.elevenlabs_api_key,
                    "Content-Type": "application/json",
                    "Accept": "audio/mpeg",
                },
                json={
                    "text": clean_text,
                    "model_id": settings.elevenlabs_tts_model,
                    "voice_settings": {
                        "stability": 0.45,
                        "similarity_boost": 0.8,
                        "style": 0.2,
                        "use_speaker_boost": True,
                    },
                },
            )
            response.raise_for_status()

        audio_bytes = response.content

        logger.info(
            "interviewer_speech_generated",
            model=settings.elevenlabs_tts_model,
            voice_id=selected_voice_id,
            bytes=len(audio_bytes),
        )

        return {
            "success": True,
            "audio_base64": base64.b64encode(audio_bytes).decode("ascii"),
            "mime_type": "audio/mpeg",
            "model": settings.elevenlabs_tts_model,
            "voice_id": selected_voice_id,
        }

    except httpx.HTTPStatusError as e:
        error_detail = e.response.text[:500] if e.response is not None else str(e)
        logger.exception(
            "interviewer_speech_failed",
            error=error_detail,
            status_code=e.response.status_code if e.response is not None else None,
            model=settings.elevenlabs_tts_model,
            voice_id=selected_voice_id,
        )
        return {
            "success": False,
            "error": error_detail,
        }

    except Exception as e:
        logger.exception(
            "interviewer_speech_failed",
            error=str(e),
            model=settings.elevenlabs_tts_model,
            voice_id=selected_voice_id,
        )
        return {
            "success": False,
            "error": str(e),
        }