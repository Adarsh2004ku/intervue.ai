"""Tests for LangGraph agents."""
import os
import pytest
from ai.agents.state import InterviewState
from ai.agents.planner import planner_agent
from ai.agents.evaluator import evaluator_agent
from ai.agents.coach import coach_agent


class TestInterviewState:
    def test_state_has_required_fields(self):
        """InterviewState should have all required fields."""
        state = InterviewState(
            user_id="test-user",
            interview_id="test-interview",
            resume_id="test-resume",
            job_role="Software Engineer",
            job_description="Build backend APIs and distributed services.",
            resume_summary={"skills": ["Python"], "projects": ["API platform"]},
            difficulty="medium",
            interview_plan=[],
            questions=[],
            answers=[],
            evaluations=[],
            speech_metrics=[],
            behavior_data=[],
            current_index=0,
            weak_topics=[],
            strong_topics=[],
            session_topic_scores={},
            interview_mode="faang",
            difficulty_profile="beginner",
            retrieved_chunks=[],
            report=None,
        )
        assert state["user_id"] == "test-user"
        assert state["current_index"] == 0


class TestPlannerAgent:
    @pytest.mark.skipif(
        not os.getenv("GOOGLE_API_KEY", "").startswith("AI"),
        reason="Requires real Gemini API key"
    )
    def test_planner_returns_plan(self):
        """Planner should return difficulty and interview plan."""
        import os
        state = InterviewState(
            user_id="test-user",
            interview_id="test-interview",
            resume_id="test-resume",
            job_role="Software Engineer at Google",
            job_description="Design scalable services and debug production systems.",
            resume_summary={"skills": ["Python"], "projects": ["Distributed API"]},
            difficulty="",
            interview_plan=[],
            questions=[],
            answers=[],
            evaluations=[],
            speech_metrics=[],
            behavior_data=[],
            current_index=0,
            weak_topics=[],
            strong_topics=[],
            session_topic_scores={},
            interview_mode="faang",
            difficulty_profile="beginner",
            retrieved_chunks=[],
            report=None,
        )
        result = planner_agent(state)
        assert "difficulty" in result
        assert "interview_plan" in result
        assert result["difficulty"] in ["easy", "medium", "hard"]


class TestEvaluatorAgent:
    @pytest.mark.skipif(
        not os.getenv("GOOGLE_API_KEY", "").startswith("AI"),
        reason="Requires real Gemini API key"
    )
    def test_evaluator_scores_answer(self):
        """Evaluator should return scores between 0-100."""
        import os
        state = {
            "questions": [{"text": "Explain the difference between a list and a tuple in Python."}],
            "answers": [{"transcript": "Lists are mutable and tuples are immutable. Lists use square brackets."}],
            "evaluations": [],
            "session_topic_scores": {},
        }
        result = evaluator_agent(state)
        assert "evaluations" in result
        assert len(result["evaluations"]) == 1
        eval_data = result["evaluations"][0]
        assert 0 <= eval_data["score"] <= 100
        assert 0 <= eval_data["accuracy_score"] <= 100
