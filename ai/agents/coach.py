import json
from backend.core.config import settings
from backend.db.session import supabase
from ai.agents.llm import invoke_llm_text
from ai.agents.state import InterviewState
from backend.core.logging import get_logger

logger = get_logger("coach_agent")

"""
Coach Agent — generates the final interview report.
Aggregates all evaluations, speech metrics, and behavior data.
Produces: overall score, per-topic feedback, improvement plan,
strengths, interview readiness, and next session focus.
Also updates user_topic_profiles in the database.
"""


def _update_topic_profiles(user_id: str, session_scores: dict):
    """Write updated topic scores back to user_topic_profiles."""
    for topic, score in session_scores.items():
        try:
            supabase.rpc(
                "upsert_topic_score",
                {"p_user_id": user_id, "p_topic": topic, "p_new_score": score},
            ).execute()
        except Exception as e:
            logger.warning("topic_profile_update_failed", topic=topic, error=str(e))


def _update_difficulty_profile(user_id: str, overall_score: int):
    """Recalibrate user's difficulty profile based on overall score."""
    if overall_score >= 75:
        new_profile = "advanced"
    elif overall_score >= 50:
        new_profile = "intermediate"
    else:
        new_profile = "beginner"

    try:
        supabase.table("users").update(
            {"difficulty_profile": new_profile}
        ).eq("id", user_id).execute()
        logger.info("difficulty_recalibrated", new_profile=new_profile)
    except Exception as e:
        logger.warning("difficulty_update_failed", error=str(e))


def coach_agent(state: InterviewState) -> dict:
    """
    Generate the final interview report and update user profiles.
    Returns updated state with 'report' populated.
    """
    evaluations = state.get("evaluations", [])
    speech_metrics = state.get("speech_metrics", [])
    behavior_data = state.get("behavior_data", [])
    questions = state.get("questions", [])

    if not evaluations:
        return {"report": {"overall_score": 0, "grade": "F", "feedback": "No evaluations available"}}

    # Calculate average scores
    avg_score = sum(e.get("score", 0) for e in evaluations) / len(evaluations)
    avg_accuracy = sum(e.get("accuracy_score", 0) for e in evaluations) / len(evaluations)
    avg_clarity = sum(e.get("clarity_score", 0) for e in evaluations) / len(evaluations)
    avg_depth = sum(e.get("depth_score", 0) for e in evaluations) / len(evaluations)

    # Build detailed Q&A summary for the LLM
    qa_summary = ""
    for i, (q, e) in enumerate(zip(questions, evaluations)):
        a = state["answers"][i] if i < len(state.get("answers", [])) else {}
        s = speech_metrics[i] if i < len(speech_metrics) else {}
        qa_summary += f"""
        Q{i+1}: {q.get('text', '')}
        A: {a.get('transcript', 'N/A')[:200]}
        Score: {e.get('score', 0)}/100 (Accuracy: {e.get('accuracy_score', 0)}, Clarity: {e.get('clarity_score', 0)}, Depth: {e.get('depth_score', 0)})
        Reasoning: {e.get('cot_reasoning', 'N/A')[:150]}
        Speech: WPM={s.get('wpm', 'N/A')}, Fillers={s.get('filler_count', 'N/A')}
        ---
        """

    prompt = f"""You are a career coach reviewing an interview session.
        Average Scores: Overall={avg_score:.0f}, Accuracy={avg_accuracy:.0f}, Clarity={avg_clarity:.0f}, Depth={avg_depth:.0f}

        Full Q&A Summary:
        {qa_summary[:6000]}

        Generate a comprehensive report with:

        1. overall_score (integer 0-100)
        2. grade (A/B/C/D/F based on score: A>=85, B>=70, C>=55, D>=40, F<40)
        3. per_topic_feedback: {{topic: {{score, strengths, gaps}}}}
        4. speech_summary: {{pace_rating, filler_rating, clarity_rating}}
        5. improvement_plan: [{{priority: 1-3, topic, action, resource, estimated_time, why}}]
        6. strengths_to_highlight: list of topics where score > 75
        7. interview_readiness: "not_ready" | "almost_ready" | "ready"
        8. next_session_focus: top 2 topics to prioritize

        Return ONLY valid JSON with these exact keys."""

    try:
        content = invoke_llm_text(
            prompt,
            temperature=0.3,
            request_timeout=20,
            purpose="coach_report",
        ).strip()
        if content.startswith("```"):
            parts = content.split("```")
            if len(parts) >= 2:
                content = parts[1]
            if content.startswith("json"):
                content = content[4:]

        report = json.loads(content.strip())
        report["overall_score"] = int(avg_score)
        report["grade"] = (
            "A" if avg_score >= 85 else
            "B" if avg_score >= 70 else
            "C" if avg_score >= 55 else
            "D" if avg_score >= 40 else "F"
        )

        logger.info(
            "report_generated",
            overall_score=report["overall_score"],
            grade=report["grade"],
        )

    except (json.JSONDecodeError, Exception) as e:
        logger.error("coach_report_failed", error=str(e))
        report = {
            "overall_score": int(avg_score),
            "grade": "A" if avg_score >= 85 else "B" if avg_score >= 70 else "C" if avg_score >= 55 else "D" if avg_score >= 40 else "F",
            "per_topic_feedback": {},
            "speech_summary": {},
            "improvement_plan": [],
            "strengths_to_highlight": [],
            "interview_readiness": "almost_ready",
            "next_session_focus": [],
        }

    # Update user profiles in the database
    user_id = state.get("user_id", "")
    session_scores = state.get("session_topic_scores", {})
    if user_id and session_scores:
        _update_topic_profiles(user_id, session_scores)
        _update_difficulty_profile(user_id, int(avg_score))

    return {"report": report}
