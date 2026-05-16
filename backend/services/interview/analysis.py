import asyncio
import time

from ai.graph.builder import run_question_turn
from backend.core.config import settings
from backend.core.logging import get_logger
from backend.services.audio.gemini_stt import transcribe_and_evaluate
from backend.services.cost_tracking import (
    estimate_elevenlabs_stt_cost_inr,
    get_interview_cost_summary,
    record_ai_cost,
    record_vision_cost,
)
from backend.services.interview.repository import (
    ensure_question,
    fetch_resume_for_user,
    fetch_questions_for_interview,
    get_interview_for_user,
    insert_answer,
    insert_question,
)
from backend.services.interview.session_state import (
    get_agent_state,
    interview_sessions,
    set_agent_state,
    with_session_interview_context,
)
from backend.services.vision.behavior import aggregate_behavior_analysis, analyze_frame


logger = get_logger("interview_analysis")


async def analyze_frame_submission(
    *,
    interview_id: str,
    user: dict,
    frame_bytes: bytes,
    mime_type: str,
) -> dict:
    get_interview_for_user(interview_id, user)
    started_at = time.perf_counter()

    result = await analyze_frame(
        frame_bytes=frame_bytes,
        mime_type=mime_type,
    )
    latency_ms = round((time.perf_counter() - started_at) * 1000)
    cost_record = record_vision_cost(
        interview_id=interview_id,
        result=result,
        latency_ms=latency_ms,
    )
    interview_sessions[interview_id]["frames"].append(result)

    return {
        "success": True,
        "analysis": result,
        "cost": cost_record,
        "session_cost": get_interview_cost_summary(interview_id),
    }


async def analyze_audio_submission(
    *,
    interview_id: str,
    user: dict,
    question: str,
    question_id: str | None,
    duration_sec: float | None,
    audio_bytes: bytes,
    mime_type: str,
) -> dict:
    interview = with_session_interview_context(
        interview_id,
        get_interview_for_user(interview_id, user),
    )
    started_at = time.perf_counter()

    result = await transcribe_and_evaluate(
        audio_bytes=audio_bytes,
        question=question,
        mime_type=mime_type,
    )
    latency_ms = round((time.perf_counter() - started_at) * 1000)
    is_billable = bool(result.pop("_billable", False))
    cost_record = None

    if is_billable:
        cost_record = record_ai_cost(
            interview_id=interview_id,
            model=result.get("model") or settings.elevenlabs_stt_model,
            call_type="speech_to_text",
            cost_inr=estimate_elevenlabs_stt_cost_inr(duration_sec),
            latency_ms=latency_ms,
        )

    interview_sessions[interview_id]["audio"].append(result)
    question_row = ensure_question(
        interview_id=interview_id,
        interview=interview,
        question_text=question,
        question_id=question_id,
    )

    try:
        insert_answer({
            "question_id": question_row["id"],
            "answer_text": result.get("transcript") or "",
            "score": result.get("score"),
            "accuracy_score": result.get("accuracy_score"),
            "clarity_score": result.get("clarity_score"),
            "depth_score": result.get("depth_score"),
            "cot_reasoning": result.get("reasoning") or "",
            "rubric_json": result,
            "behavior_score": result.get("confidence_score"),
            "latency_ms": latency_ms,
            "audio_duration_sec": duration_sec,
        })
    except Exception as e:
        logger.exception(
            "answer_store_failed",
            interview_id=interview_id,
            question_id=question_row.get("id"),
            error=str(e),
        )

    try:
        previous_questions = fetch_questions_for_interview(interview_id)
        agent_state = get_agent_state(interview_id)
        resume_summary = agent_state.get("resume_summary") or {}
        if not resume_summary and interview.get("resume_id"):
            resume = fetch_resume_for_user(interview["resume_id"], user) or {}
            resume_summary = resume.get("parsed_json") or {}

        agent_state = {
            "user_id": user["sub"],
            "interview_id": interview_id,
            "resume_id": interview.get("resume_id") or "",
            "job_role": interview.get("job_role") or "General",
            "job_description": interview.get("job_description") or "",
            "resume_summary": resume_summary if isinstance(resume_summary, dict) else {},
            "difficulty": agent_state.get("difficulty", "medium"),
            "interview_plan": agent_state.get("interview_plan", []),
            "questions": previous_questions,
            "answers": [
                *agent_state.get("answers", []),
                {"transcript": result.get("transcript") or ""},
            ],
            "evaluations": [
                *agent_state.get("evaluations", []),
                {
                    **result,
                    "cot_reasoning": result.get("reasoning") or result.get("cot_reasoning") or "",
                },
            ],
            "speech_metrics": agent_state.get("speech_metrics", []),
            "behavior_data": interview_sessions[interview_id]["frames"],
            "current_index": len(previous_questions),
            "weak_topics": agent_state.get("weak_topics", []),
            "strong_topics": agent_state.get("strong_topics", []),
            "session_topic_scores": agent_state.get("session_topic_scores", {}),
            "interview_mode": interview.get("interview_mode") or "faang",
            "difficulty_profile": agent_state.get("difficulty_profile", "beginner"),
            "retrieved_chunks": agent_state.get("retrieved_chunks", []),
            "report": agent_state.get("report"),
        }
        agent_state = await asyncio.to_thread(
            run_question_turn,
            agent_state,
            include_planner=not bool(agent_state.get("interview_plan")),
        )
        next_payload = agent_state["questions"][-1]
        set_agent_state(interview_id, agent_state)
        next_question = insert_question(interview_id, next_payload)
    except Exception as e:
        logger.exception(
            "next_question_create_failed",
            interview_id=interview_id,
            error=str(e),
        )
        next_question = None

    return {
        "success": True,
        "evaluation": result,
        "next_question": next_question,
        "cost": cost_record,
        "session_cost": get_interview_cost_summary(interview_id),
    }


def summarize_behavior_for_user(interview_id: str, user: dict) -> dict:
    get_interview_for_user(interview_id, user)
    return {
        "success": True,
        "summary": aggregate_behavior_analysis(interview_sessions[interview_id]["frames"]),
    }
