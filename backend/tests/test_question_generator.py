from types import SimpleNamespace

from ai.agents import generator
from ai.agents import llm as llm_provider
from ai.agents.generator import question_payload
from backend.core.config import settings


def test_local_fallback_rotates_first_question_by_interview_seed():
    questions = {
        question_payload(
            mode="faang",
            job_role="Backend Engineer",
            order_idx=0,
            fallback_seed=f"interview-{index}",
        )["text"]
        for index in range(8)
    }

    assert len(questions) > 1


def test_local_fallback_uses_resume_and_job_description_terms():
    payload = question_payload(
        mode="faang",
        job_role="Platform Engineer",
        order_idx=0,
        job_description="Own Kubernetes reliability, observability, and incident response.",
        resume_context="Built Prometheus dashboards and automated rollout checks.",
    )

    text = payload["text"].lower()
    assert "platform engineer" in text
    assert any(term in text for term in ["kubernetes", "observability", "prometheus"])


def test_system_design_stage_generates_case_style_prompt():
    payload = question_payload(
        mode="faang",
        job_role="Staff Backend Engineer",
        order_idx=3,
        topic_info={
            "phase": "system_design_case",
            "category": "System Design",
            "topic": "high-volume interview scheduling service",
            "focus": "calendar conflicts, retries, availability, observability",
            "success_signal": "trade-off quality",
        },
    )

    text = payload["text"].lower()
    assert "system design" in text
    assert "requirements" in text
    assert any(term in text for term in ["api", "data model", "scaling", "reliability"])


def test_product_case_stage_generates_case_study_prompt():
    payload = question_payload(
        mode="startup",
        job_role="Product Engineer",
        order_idx=0,
        topic_info={
            "phase": "product_case",
            "category": "Product Case Study",
            "topic": "activation drop after onboarding launch",
            "focus": "prioritization, metrics, launch risk",
        },
    )

    text = payload["text"].lower()
    assert "case" in text
    assert any(term in text for term in ["metric", "prioritize", "hypotheses", "data"])


def test_gemini_question_generation_uses_supported_timeout(monkeypatch):
    captured_kwargs = {}

    class FakeGemini:
        def __init__(self, **kwargs):
            captured_kwargs.update(kwargs)

        def invoke(self, prompt):
            return SimpleNamespace(
                content='{"text":"How did you validate a hard backend migration?",'
                '"category":"Interview","topic":"Backend Engineer",'
                '"difficulty":"adaptive","why_asked":"Targets validation.",'
                '"is_weakness_focused":false}'
            )

    monkeypatch.setattr(llm_provider, "ChatGoogleGenerativeAI", FakeGemini)

    generator.generate_question_payload_sync(
        mode="faang",
        job_role="Backend Engineer",
        order_idx=0,
    )

    assert captured_kwargs["request_timeout"] >= 10


def test_groq_fallback_is_used_when_gemini_fails(monkeypatch):
    class BrokenGemini:
        def __init__(self, **kwargs):
            pass

        def invoke(self, prompt):
            raise RuntimeError("gemini unavailable")

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"text":"Which FastAPI service best proves your backend fit?",'
                                '"category":"Interview","topic":"Backend Engineer",'
                                '"difficulty":"adaptive","why_asked":"Targets Groq fallback.",'
                                '"is_weakness_focused":false}'
                            )
                        }
                    }
                ]
            }

    class FakeClient:
        def __init__(self, timeout):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def post(self, url, headers, json):
            assert headers["Authorization"].startswith("Bearer ")
            assert json["model"] == settings.groq_model
            return FakeResponse()

    monkeypatch.setattr(llm_provider, "ChatGoogleGenerativeAI", BrokenGemini)
    monkeypatch.setattr(llm_provider.httpx, "Client", FakeClient)
    monkeypatch.setattr(settings, "groq_api_key", "gsk_test_key")

    payload = generator.generate_question_payload_sync(
        mode="faang",
        job_role="Backend Engineer",
        order_idx=0,
    )

    assert payload["text"] == "Which FastAPI service best proves your backend fit?"


def test_empty_gemini_response_uses_groq_fallback(monkeypatch):
    class EmptyGemini:
        def __init__(self, **kwargs):
            pass

        def invoke(self, prompt):
            return SimpleNamespace(content="   ")

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"text":"How would you debug a production incident in FastAPI?",'
                                '"category":"Interview","topic":"Backend Engineer",'
                                '"difficulty":"adaptive","why_asked":"Gemini returned empty content.",'
                                '"is_weakness_focused":false}'
                            )
                        }
                    }
                ]
            }

    class FakeClient:
        def __init__(self, timeout):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def post(self, url, headers, json):
            return FakeResponse()

    monkeypatch.setattr(llm_provider, "_GEMINI_COOLDOWN_UNTIL", 0.0)
    monkeypatch.setattr(llm_provider, "ChatGoogleGenerativeAI", EmptyGemini)
    monkeypatch.setattr(llm_provider.httpx, "Client", FakeClient)
    monkeypatch.setattr(settings, "groq_api_key", "gsk_test_key")

    payload = generator.generate_question_payload_sync(
        mode="faang",
        job_role="Backend Engineer",
        order_idx=0,
    )

    assert payload["text"] == "How would you debug a production incident in FastAPI?"


def test_gemini_rate_limit_skips_to_groq_during_cooldown(monkeypatch):
    calls = {"gemini": 0, "groq": 0}

    class RateLimitedGemini:
        def __init__(self, **kwargs):
            pass

        def invoke(self, prompt):
            calls["gemini"] += 1
            raise RuntimeError("429 RESOURCE_EXHAUSTED quota exceeded")

    class UnexpectedGemini:
        def __init__(self, **kwargs):
            raise AssertionError("Gemini should be skipped during cooldown")

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            calls["groq"] += 1
            return {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"text":"How would you design a resilient interview scheduler?",'
                                '"category":"System Design","topic":"Interview scheduling",'
                                '"difficulty":"adaptive","why_asked":"Uses Groq during Gemini cooldown.",'
                                '"is_weakness_focused":false}'
                            )
                        }
                    }
                ]
            }

    class FakeClient:
        def __init__(self, timeout):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def post(self, url, headers, json):
            assert headers["Authorization"].startswith("Bearer ")
            return FakeResponse()

    monkeypatch.setattr(llm_provider, "_GEMINI_COOLDOWN_UNTIL", 0.0)
    monkeypatch.setattr(llm_provider, "ChatGoogleGenerativeAI", RateLimitedGemini)
    monkeypatch.setattr(llm_provider.httpx, "Client", FakeClient)
    monkeypatch.setattr(settings, "groq_api_key", "gsk_test_key")
    monkeypatch.setattr(settings, "gemini_cooldown_seconds", 60)

    first_payload = generator.generate_question_payload_sync(
        mode="faang",
        job_role="Backend Engineer",
        order_idx=0,
    )

    monkeypatch.setattr(llm_provider, "ChatGoogleGenerativeAI", UnexpectedGemini)

    second_payload = generator.generate_question_payload_sync(
        mode="faang",
        job_role="Backend Engineer",
        order_idx=1,
    )

    assert calls == {"gemini": 1, "groq": 2}
    assert first_payload["text"] == "How would you design a resilient interview scheduler?"
    assert second_payload["text"] == "How would you design a resilient interview scheduler?"
