import base64
import json
import asyncio

import google.genai as genai

from backend.core.config import settings
from backend.core.logging import get_logger


"""
Gemini native audio transcription + evaluation.
Uses the modern google-genai SDK.
"""

logger = get_logger("gemini_stt")

client = genai.Client(
    api_key=settings.google_api_key
)


async def transcribe_audio(
    audio_bytes: bytes,
    mime_type: str = "audio/wav"
) -> str:
    """
    Transcribe audio bytes to text using Gemini.
    """

    audio_b64 = base64.b64encode(audio_bytes).decode()

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            {
                "inline_data": {
                    "mime_type": mime_type,
                    "data": audio_b64,
                }
            },
            "Transcribe this audio exactly as spoken. Return ONLY the transcript text.",
        ],
    )

    transcript = response.text.strip()

    logger.info(
        "audio_transcribed",
        length=len(transcript),
    )

    return transcript


async def transcribe_and_evaluate(
    audio_bytes: bytes,
    question: str,
    mime_type: str = "audio/wav",
) -> dict:
    """
    Transcribe audio and evaluate interview answer.
    """

    audio_b64 = base64.b64encode(audio_bytes).decode()

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            {
                "inline_data": {
                    "mime_type": mime_type,
                    "data": audio_b64,
                }
            },
            f"""
First, transcribe this audio answer exactly as spoken.

Then evaluate the transcribed answer for this interview question:

"{question}"

Return ONLY valid JSON:

{{
    "transcript": "exact words spoken",
    "score": 75,
    "accuracy_score": 80,
    "clarity_score": 70,
    "depth_score": 65,
    "cot_reasoning": "brief explanation"
}}

Scoring:
- accuracy_score: factual correctness
- clarity_score: communication quality
- depth_score: depth of understanding
- score: weighted average
""",
        ],
    )

    raw = response.text.strip()

    # Remove markdown fences if Gemini wraps JSON
    if raw.startswith("```"):
        raw = raw.replace("```json", "").replace("```", "").strip()

    try:
        result = json.loads(raw)

        logger.info(
            "audio_transcribed_and_evaluated",
            transcript_len=len(result.get("transcript", "")),
            score=result.get("score", 0),
        )

        return result

    except json.JSONDecodeError as e:
        logger.error(
            "gemini_audio_parse_failed",
            error=str(e),
            raw=raw[:200],
        )

        return {
            "transcript": raw[:500],
            "score": 0,
            "accuracy_score": 0,
            "clarity_score": 0,
            "depth_score": 0,
            "cot_reasoning": "Failed to parse evaluation response",
        }


async def transcribe_and_evaluate_with_retry(
    audio_bytes: bytes,
    question: str,
    max_retries: int = 3,
) -> dict:
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
            if "429" in str(e) and attempt < max_retries - 1:

                wait_time = 2 ** attempt

                logger.warning(
                    "rate_limit_hit",
                    attempt=attempt + 1,
                    wait_seconds=wait_time,
                )

                await asyncio.sleep(wait_time)

            else:
                logger.error(
                    "transcription_failed_after_retries",
                    error=str(e),
                    attempts=attempt + 1,
                )

                return {
                    "transcript": "",
                    "score": 0,
                    "accuracy_score": 0,
                    "clarity_score": 0,
                    "depth_score": 0,
                    "cot_reasoning": f"Transcription failed: {str(e)}",
                }