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
