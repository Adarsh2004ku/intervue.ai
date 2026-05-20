import re
from statistics import mean

import httpx

from backend.core.config import settings
from backend.core.logging import get_logger


logger = get_logger("elevenlabs_stt")

ELEVENLABS_STT_URL = "https://api.elevenlabs.io/v1/speech-to-text"
ELEVENLABS_AUTH_ERROR = (
    "ElevenLabs speech-to-text is not authorized. Check ELEVENLABS_API_KEY "
    "and your ElevenLabs account access, then retry this answer."
)
ELEVENLABS_UNAVAILABLE_ERROR = (
    "ElevenLabs speech-to-text is temporarily unavailable. Your answer was "
    "not transcribed, so scoring could not be completed for this response."
)

STOP_WORDS = {
    "a", "an", "and", "are", "as", "at",
    "be", "by", "for", "from", "how", "i", "in", "is", "it", "me", "my",
    "of", "on", "or", "that", "the", "this", "to", "was", "what", "when",
    "where", "with", "you", "your",
}

FILLER_WORDS = {
    "um", "uh", "erm", "hmm", "like",
    "basically", "actually", "literally",
}


def _clamp_score(value: float) -> int:
    return max(0, min(100, round(value)))


def _keywords(text: str) -> set[str]:
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9+#.-]*", text.lower())
    return {
        word
        for word in words
        if len(word) > 2 and word not in STOP_WORDS
    }


def _extract_transcript(response: dict) -> str:
    text = response.get("text")
    if isinstance(text, str):
        return text.strip()

    transcripts = response.get("transcripts")
    if isinstance(transcripts, list):
        return " ".join(
            item.get("text", "")
            for item in transcripts
            if isinstance(item, dict)
        ).strip()

    return ""


def _average_word_confidence(words: list[dict]) -> float | None:
    scores = []
    for word in words:
        logprob = word.get("logprob")
        if isinstance(logprob, (int, float)):
            scores.append(max(0.0, min(1.0, 1 + (logprob / 5))))

    if not scores:
        return None

    return mean(scores)


def _evaluate_transcript(transcript: str, question: str, stt_response: dict) -> dict:
    answer_words = re.findall(r"[a-zA-Z][a-zA-Z0-9']*", transcript.lower())
    word_count = len(answer_words)
    filler_count = sum(1 for word in answer_words if word in FILLER_WORDS)
    stopword_count = sum(1 for word in answer_words if word in STOP_WORDS)

    question_keywords = _keywords(question)
    answer_keywords = _keywords(transcript)
    keyword_overlap = (
        len(question_keywords & answer_keywords) / len(question_keywords)
        if question_keywords
        else 0
    )

    words = stt_response.get("words")
    word_confidence = _average_word_confidence(words if isinstance(words, list) else [])
    language_probability = stt_response.get("language_probability")
    if not isinstance(language_probability, (int, float)):
        language_probability = word_confidence if word_confidence is not None else 0.75

    filler_ratio = filler_count / word_count if word_count else 1
    depth_score = _clamp_score(min(1, word_count / 90) * 100)
    clarity_score = _clamp_score((language_probability * 100) - (filler_ratio * 120))
    accuracy_score = _clamp_score(45 + (keyword_overlap * 35) + (depth_score * 0.2))
    confidence_score = _clamp_score(85 - (filler_ratio * 250) + min(10, word_count / 20))
    communication_score = _clamp_score(
        (clarity_score + confidence_score + depth_score) / 3
    )
    score = _clamp_score(
        (
            accuracy_score
            + clarity_score
            + depth_score
            + confidence_score
            + communication_score
        )
        / 5
    )

    if not transcript:
        reasoning = "ElevenLabs did not return a transcript for this answer."
    else:
        reasoning = (
            f"ElevenLabs transcribed {word_count} words. "
            f"Keyword overlap with the question was {round(keyword_overlap * 100)}%, "
            f"with {filler_count} detected filler words."
        )

    return {
        "transcript": transcript,
        "score": score,
        "accuracy_score": accuracy_score,
        "clarity_score": clarity_score,
        "depth_score": depth_score,
        "confidence_score": confidence_score,
        "communication_score": communication_score,
        "reasoning": reasoning,
        "word_count": word_count,
        "stopword_count": stopword_count,
        "filler_count": filler_count,
        "keyword_overlap_percent": round(keyword_overlap * 100),
        "words_per_minute": 0,
        "provider": "elevenlabs",
        "model": settings.elevenlabs_stt_model,
    }


def _unavailable_result(reasoning: str, error_code: str) -> dict:
    return {
        "transcript": "",
        "score": 0,
        "accuracy_score": 0,
        "clarity_score": 0,
        "depth_score": 0,
        "confidence_score": 0,
        "communication_score": 0,
        "reasoning": reasoning,
        "word_count": 0,
        "stopword_count": 0,
        "filler_count": 0,
        "keyword_overlap_percent": 0,
        "words_per_minute": 0,
        "provider": "elevenlabs",
        "model": settings.elevenlabs_stt_model,
        "analysis_unavailable": True,
        "error_code": error_code,
        "_billable": False,
    }


async def _transcribe_with_elevenlabs(
    audio_bytes: bytes,
    mime_type: str,
) -> dict:
    if not settings.elevenlabs_api_key:
        raise ValueError("ELEVENLABS_API_KEY is not configured")

    files = {
        "file": (
            "answer.webm",
            audio_bytes,
            mime_type,
        )
    }
    data = {
        "model_id": settings.elevenlabs_stt_model,
        "tag_audio_events": "true",
        "diarize": "false",
    }

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            ELEVENLABS_STT_URL,
            headers={
                "xi-api-key": settings.elevenlabs_api_key,
            },
            data=data,
            files=files,
        )
        response.raise_for_status()
        return response.json()


async def transcribe_and_evaluate(
    audio_bytes: bytes,
    question: str,
    mime_type: str = "audio/webm",
) -> dict:
    try:
        stt_response = await _transcribe_with_elevenlabs(
            audio_bytes=audio_bytes,
            mime_type=mime_type,
        )
        transcript = _extract_transcript(stt_response)
        result = _evaluate_transcript(
            transcript=transcript,
            question=question,
            stt_response=stt_response,
        )

        logger.info(
            "audio_transcribed_with_elevenlabs",
            model=settings.elevenlabs_stt_model,
            transcript_length=len(transcript),
        )

        result["_billable"] = True
        return result

    except httpx.HTTPStatusError as e:
        status_code = e.response.status_code if e.response is not None else None
        error_detail = e.response.text[:500] if e.response is not None else str(e)
        logger.warning(
            "audio_evaluation_provider_http_error",
            provider="elevenlabs",
            status_code=status_code,
            error=error_detail,
        )

        if status_code in {401, 403}:
            return _unavailable_result(
                ELEVENLABS_AUTH_ERROR,
                "elevenlabs_unauthorized",
            )

        return _unavailable_result(
            ELEVENLABS_UNAVAILABLE_ERROR,
            "elevenlabs_unavailable",
        )

    except Exception as e:
        logger.exception(
            "audio_evaluation_failed",
            provider="elevenlabs",
            error=str(e),
        )

        return _unavailable_result(
            ELEVENLABS_UNAVAILABLE_ERROR,
            "elevenlabs_unavailable",
        )
