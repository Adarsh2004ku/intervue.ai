from typing import Any

from ai.agents.generator import clean_job_description, job_description_terms
from backend.db.session import supabase


def _grade(score: int) -> str:
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"


def _readiness(score: int) -> str:
    if score >= 75:
        return "ready"
    if score >= 55:
        return "almost_ready"
    return "not_ready"


def _average(values: list[int]) -> int:
    values = [value for value in values if isinstance(value, int)]
    return round(sum(values) / len(values)) if values else 0


def build_report_payload(
    interview: dict[str, Any],
    requested_score: int | None,
    behavior_summary: dict[str, Any] | None,
) -> dict[str, Any]:
    questions_result = (
        supabase.table("questions")
        .select("*")
        .eq("interview_id", interview["id"])
        .order("order_idx")
        .execute()
    )
    questions = questions_result.data or []
    question_ids = [q["id"] for q in questions if q.get("id")]

    answers = []
    if question_ids:
        answers_result = (
            supabase.table("answers")
            .select("*")
            .in_("question_id", question_ids)
            .order("created_at")
            .execute()
        )
        answers = answers_result.data or []

    question_by_id = {q["id"]: q for q in questions}
    scores = [int(a.get("score") or 0) for a in answers if a.get("score") is not None]
    overall_score = requested_score if requested_score is not None else _average(scores)
    overall_score = max(0, min(100, overall_score or 0))

    feedback_json: dict[str, Any] = {}
    for answer in answers:
        question = question_by_id.get(answer.get("question_id"), {})
        topic = question.get("topic") or question.get("category") or "General"
        feedback_json[topic] = {
            "question": question.get("text", ""),
            "score": answer.get("score"),
            "accuracy": answer.get("accuracy_score"),
            "clarity": answer.get("clarity_score"),
            "depth": answer.get("depth_score"),
            "reasoning": answer.get("cot_reasoning") or "",
        }

    low_topics = [
        topic
        for topic, details in feedback_json.items()
        if int(details.get("score") or 0) < 70
    ]
    strong_topics = [
        topic
        for topic, details in feedback_json.items()
        if int(details.get("score") or 0) >= 75
    ]

    job_description = clean_job_description(interview.get("job_description"))
    role_focus = job_description_terms(job_description)
    improvement_topics = (
        low_topics
        or role_focus[:3]
        or [interview.get("job_role") or "Interview practice"]
    )
    improvement_resource = (
        "Map your answer directly to the pasted job description and back it with resume evidence."
        if job_description
        else "Review your saved transcript and repeat the question out loud."
    )
    improvement_plan = [
        {
            "priority": index + 1,
            "topic": topic,
            "action": "Practice a concise STAR answer, then add concrete metrics and trade-offs.",
            "resource": improvement_resource,
            "estimated_time": "20 minutes",
            "why": (
                "This was identified from your latest interview session and pasted job description."
                if job_description
                else "This was identified from your latest interview session."
            ),
        }
        for index, topic in enumerate(improvement_topics[:3])
    ]

    speech_summary = {
        "answer_count": len(answers),
        "average_clarity": _average([int(a.get("clarity_score") or 0) for a in answers]),
        "average_confidence": _average([int(a.get("behavior_score") or 0) for a in answers]),
        "behavior_summary": behavior_summary or {},
        "job_description_focus": role_focus,
    }

    return {
        "interview_id": interview["id"],
        "overall_score": overall_score,
        "grade": _grade(overall_score),
        "interview_readiness": _readiness(overall_score),
        "feedback_json": feedback_json,
        "improvement_plan": improvement_plan,
        "speech_summary": speech_summary,
        "strengths": strong_topics[:3] or ["Completed a live mock interview"],
        "next_session_focus": improvement_topics[:3],
    }
