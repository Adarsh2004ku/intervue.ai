import pytest

from backend.services.vision import behavior


@pytest.mark.asyncio
async def test_behavior_rate_limit_returns_clean_cooldown_response(monkeypatch):
    calls = {"gemini": 0}

    def rate_limited(contents):
        calls["gemini"] += 1
        raise RuntimeError(
            "429 RESOURCE_EXHAUSTED quota exceeded. Please retry in 54.3s."
        )

    def unexpected_call(contents):
        calls["gemini"] += 1
        raise AssertionError("Gemini should be skipped during cooldown")

    monkeypatch.setattr(behavior, "_GEMINI_VISION_COOLDOWN_UNTIL", 0.0)
    monkeypatch.setattr(behavior, "_generate_content", rate_limited)

    first = await behavior.analyze_frame(b"fake-frame")

    monkeypatch.setattr(behavior, "_generate_content", unexpected_call)
    second = await behavior.analyze_frame(b"fake-frame")

    assert calls == {"gemini": 1}
    assert first["analysis_unavailable"] is True
    assert first["error_code"] == "gemini_rate_limited"
    assert first["retry_after_seconds"] == 55
    assert "RESOURCE_EXHAUSTED" not in first["notes"]
    assert second["analysis_unavailable"] is True
    assert second["error_code"] == "gemini_rate_limited"


def test_aggregate_behavior_analysis_ignores_unavailable_frames():
    summary = behavior.aggregate_behavior_analysis([
        {
            "analysis_unavailable": True,
            "engagement_score": 50,
            "confidence_score": 50,
            "professionalism_score": 50,
            "nervousness_score": 50,
            "eye_contact": True,
            "distracted": False,
            "emotion": "neutral",
        },
        {
            "engagement_score": 90,
            "confidence_score": 80,
            "professionalism_score": 85,
            "nervousness_score": 20,
            "eye_contact": False,
            "distracted": True,
            "emotion": "focused",
        },
    ])

    assert summary["overall_engagement"] == 90
    assert summary["overall_confidence"] == 80
    assert summary["overall_professionalism"] == 85
    assert summary["overall_nervousness"] == 20
    assert summary["eye_contact_ratio"] == 0
    assert summary["distraction_ratio"] == 100
    assert summary["dominant_emotion"] == "focused"


def test_aggregate_behavior_analysis_reports_when_all_frames_unavailable():
    summary = behavior.aggregate_behavior_analysis([
        {
            "analysis_unavailable": True,
            "notes": "AI behavior analysis is temporarily unavailable.",
        }
    ])

    assert summary["overall_engagement"] == 0
    assert summary["dominant_emotion"] == "neutral"
    assert "unavailable" in summary["behavior_summary"]
