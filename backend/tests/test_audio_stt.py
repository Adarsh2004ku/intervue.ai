import httpx
import pytest

from backend.services.audio import elevenlabs_stt


def test_elevenlabs_stt_evaluator_reports_correct_provider():
    result = elevenlabs_stt._evaluate_transcript(
        transcript="I designed a FastAPI service with PostgreSQL migrations and retry handling.",
        question="How did you design the FastAPI service?",
        stt_response={"language_probability": 0.98},
    )

    assert result["provider"] == "elevenlabs"
    assert result["model"]
    assert result["transcript"].startswith("I designed")
    assert result["score"] > 0
    assert result["word_count"] == 11
    assert result["stopword_count"] >= 2
    assert result["words_per_minute"] == 0


@pytest.mark.asyncio
async def test_elevenlabs_stt_unauthorized_returns_clean_unavailable_result(monkeypatch):
    async def fake_transcribe(audio_bytes: bytes, mime_type: str) -> dict:
        request = httpx.Request("POST", elevenlabs_stt.ELEVENLABS_STT_URL)
        response = httpx.Response(401, request=request, text="invalid key")
        raise httpx.HTTPStatusError(
            "Client error '401 Unauthorized'",
            request=request,
            response=response,
        )

    monkeypatch.setattr(
        elevenlabs_stt,
        "_transcribe_with_elevenlabs",
        fake_transcribe,
    )

    result = await elevenlabs_stt.transcribe_and_evaluate(
        audio_bytes=b"fake-audio",
        question="Tell me about your backend experience.",
    )

    assert result["analysis_unavailable"] is True
    assert result["error_code"] == "elevenlabs_unauthorized"
    assert result["score"] == 0
    assert "ELEVENLABS_API_KEY" in result["reasoning"]
    assert "Client error" not in result["reasoning"]
