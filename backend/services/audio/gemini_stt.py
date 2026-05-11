import asyncio
import base64
import json

from google import genai

from backend.core.config import settings
from backend.core.logging import get_logger


logger = get_logger("gemini_stt")


# =========================================================
# Gemini Client
# =========================================================
client = genai.Client(
    api_key=settings.google_api_key
)


# =========================================================
# Internal Sync Function
# =========================================================
def _generate_content(model: str, contents):

    return client.models.generate_content(
        model=model,
        contents=contents,
        config={
            "temperature": 0.2,
            "top_p": 0.8,
        }
    )


# =========================================================
# Transcribe Audio
# =========================================================
async def transcribe_audio(
    audio_bytes: bytes,
    mime_type: str = "audio/wav"
) -> str:
    """
    Transcribe audio bytes to text using Gemini.
    """

    try:

        audio_b64 = base64.b64encode(
            audio_bytes
        ).decode("utf-8")

        response = await asyncio.to_thread(
            _generate_content,
            "gemini-2.5-flash",
            [
                {
                    "inline_data": {
                        "mime_type": mime_type,
                        "data": audio_b64,
                    }
                },
                (
                    "Transcribe this audio exactly "
                    "as spoken. Return ONLY transcript text."
                ),
            ]
        )

        transcript = response.text.strip()

        logger.info(
            "audio_transcribed",
            length=len(transcript),
        )

        return transcript

    except Exception as e:

        logger.exception(
            "audio_transcription_failed",
            error=str(e)
        )

        return ""


# =========================================================
# Transcribe + Evaluate
# =========================================================
async def transcribe_and_evaluate(
    audio_bytes: bytes,
    question: str,
    mime_type: str = "audio/wav",
) -> dict:
    """
    Transcribe audio and evaluate interview answer.
    """

    try:

        audio_b64 = base64.b64encode(
            audio_bytes
        ).decode("utf-8")

        response = await asyncio.to_thread(
            _generate_content,
            "gemini-2.5-flash",
            [
                {
                    "inline_data": {
                        "mime_type": mime_type,
                        "data": audio_b64,
                    }
                },

                f"""
First transcribe this interview answer exactly.

Then evaluate the answer for this question:

\"{question}\"

Return ONLY valid JSON:

{{
    "transcript": "exact spoken words",
    "score": 75,
    "accuracy_score": 80,
    "clarity_score": 70,
    "depth_score": 65,
    "confidence_score": 78,
    "communication_score": 72,
    "reasoning": "brief evaluation"
}}

Scoring:
- accuracy_score → factual correctness
- clarity_score → communication quality
- depth_score → understanding depth
- confidence_score → speaking confidence
- communication_score → professionalism
- score → weighted average
"""
            ]
        )

        raw = response.text.strip()

        # Remove markdown
        if raw.startswith("```"):
            raw = (
                raw.replace("```json", "")
                .replace("```", "")
                .strip()
            )

        result = json.loads(raw)

        logger.info(
            "audio_evaluated",
            transcript_len=len(
                result.get("transcript", "")
            ),
            score=result.get("score", 0),
        )

        return result

    except json.JSONDecodeError as e:

        logger.warning(
            "gemini_json_parse_failed",
            error=str(e),
        )

        return {
            "transcript": "",
            "score": 0,
            "accuracy_score": 0,
            "clarity_score": 0,
            "depth_score": 0,
            "confidence_score": 0,
            "communication_score": 0,
            "reasoning": "Failed to parse Gemini response",
        }

    except Exception as e:

        logger.exception(
            "audio_evaluation_failed",
            error=str(e),
        )

        return {
            "transcript": "",
            "score": 0,
            "accuracy_score": 0,
            "clarity_score": 0,
            "depth_score": 0,
            "confidence_score": 0,
            "communication_score": 0,
            "reasoning": f"Evaluation failed: {str(e)}",
        }


# =========================================================
# Retry Wrapper
# =========================================================
async def transcribe_and_evaluate_with_retry(
    audio_bytes: bytes,
    question: str,
    max_retries: int = 3,
):
    """
    Retry wrapper with exponential backoff.
    """

    for attempt in range(max_retries):

        try:

            return await transcribe_and_evaluate(
                audio_bytes,
                question,
            )

        except Exception as e:

            if (
                "429" in str(e)
                and attempt < max_retries - 1
            ):

                wait_time = 2 ** attempt

                logger.warning(
                    "rate_limit_hit",
                    attempt=attempt + 1,
                    wait_seconds=wait_time,
                )

                await asyncio.sleep(wait_time)

            else:

                logger.error(
                    "transcription_failed",
                    error=str(e),
                    attempts=attempt + 1,
                )

                return {
                    "transcript": "",
                    "score": 0,
                    "accuracy_score": 0,
                    "clarity_score": 0,
                    "depth_score": 0,
                    "confidence_score": 0,
                    "communication_score": 0,
                    "reasoning": (
                        f"Transcription failed: {str(e)}"
                    ),
                }