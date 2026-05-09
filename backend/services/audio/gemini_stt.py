import base64,json
import google.generativeai as genai
from backend.core.config import settings
from backend.core.logging import get_logger

"""
Gemini native audio transcription + evaluation.
Sends audio bytes directly to Gemini 2.5 Flash and gets
transcript + evaluation scores in a single API call.
No Whisper model needed — saves 500MB RAM and 30s cold start.
"""

logger = get_logger("gemini_Stt")

genai.configure(api_key= settings.google_api_key)

async def transcribe_audio(audio_bytes : bytes,mime_type : str = "audio/wav")->str:
    """
    Transcribe audio bytes to text using Gemini.
    Returns the transcript string.
    """
    model = genai.GenerativeModel("gemini-2.5-flash")
    audio_b64 = base64.b64encode(audio_bytes).decode()

    response = model.generate_content(
        [
            {"inline_data": {"mime_type": mime_type, "data": audio_b64}},
            "Transcribe this audio exactly as spoken. Return ONLY the transcript text, nothing else.",
        ]
    )
    transcript = response.text.strip()
    logger.info("audio_transcribed", length = len(transcript))
    return transcript


async def transcribe_and_evaluate(
        audio_bytes: bytes,
        question :str,
        mime_type:str = "audio/wav")->dict:
    """
    Transcribe audio AND evaluate the answer in a single Gemini call.
    Returns dict with: transcript, score, accuracy_score, clarity_score,
    depth_score, cot_reasoning.
    """

    model = genai.GenerativeModel("gemini-2.5-flash")
    audio_b64 = base64.b64encode(audio_bytes).decode()


    response = model.generate_content(
        [
            {"inline_data": {"mime_type": mime_type, "data": audio_b64}},
            f"""First, transcribe this audio answer exactly as spoken.

        Then evaluate the transcribed answer for this interview question: "{question}"

        Return ONLY valid JSON with these fields:
        {{
            "transcript": "exact words spoken",
            "score": 75,
            "accuracy_score": 80,
            "clarity_score": 70,
            "depth_score": 65,
            "cot_reasoning": "one paragraph explaining the scores"
        }}

        Scoring guidelines:
        - accuracy_score: Is the answer factually correct? (0-100)
        - clarity_score: Is the answer well-structured and clearly communicated? (0-100)
        - depth_score: Does the answer demonstrate deep understanding? (0-100)
        - score: Weighted average (40% accuracy, 30% clarity, 30% depth)
        - cot_reasoning: Brief explanation of why these scores were given""",
                ]
            )
    raw = response.text.strip()
    #strip markdown code fences if gemini wraps JSON
    if raw.startswith("```"):
        parts = raw.split("```")
        if len(parts) >= 2:
            raw = parts[1]
        if raw.startswith("json"):
            raw = raw[4:]
    
    try:
        result = json.loads(raw.strip())
        logger.info(
            "audio_tramscribed_and evaluated",
            trascript_len = len(result.get("transcript","")),
            score = result.get("score",0)
        )
        return result
    except json.JSONDecodeError as e:
        logger.error("gemini_audio_parse_failed",error = str(e),raw = raw[:200])
        return{
            "transcript": raw[:500],
            "score": 0,
            "accuracy_score": 0,
            "clarity_score": 0,
            "depth_score": 0,
            "cot_reasoning": "Failed to parse evaluation response",
        }
    
async def transcribe_and_evaluate_with_retry(
        audio_bytes :bytes,
        question : str,max_retries : int = 3)->dict:
    """
    Transcribe + evaluate with exponential backoff on 429 errors.
    """
    import asyncio
    for attempt in range(max_retries):
        try :
            return await transcribe_and_evaluate(audio_bytes, question)
        except Exception as e:
            if "429" in str(e) and attempt < max_retries - 1:
                wait_time = 2**attempt  # 1s, 2s, 4s
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