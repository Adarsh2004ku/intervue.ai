from __future__ import annotations

import uuid
import time
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from ai.agents.evaluator import evaluator_agent
from ai.agents.generator import fallback_question_for_index, generator_agent
from ai.agents.planner import planner_agent
from ai.agents.retriever import retriever_agent
from ai.agents.state import InterviewState
from ai.personas.interviewer_personas import get_persona
from backend.core.config import settings
from backend.core.logging import get_logger
from backend.db.session import supabase
from backend.services.cost_tracking import (
    estimate_elevenlabs_stt_cost_inr,
    estimate_elevenlabs_tts_cost_inr,
    estimate_gemini_cost_inr,
    get_interview_cost_summary,
    record_ai_cost,
)
from backend.services.audio.elevenlabs_tts import synthesize_interviewer_speech
from backend.services.audio.gemini_stt import transcribe_and_evaluate
from backend.services.vision.behavior import analyze_frame, aggregate_behavior_analysis


logger = get_logger("interview_agent_flow")

MAX_SESSION_FRAMES = 60
MAX_SESSION_AUDIO_RESULTS = 20

interview_sessions: dict[str, dict[str, Any]] = {}


def _empty_runtime_session() -> dict[str, Any]:
    return {
        "frames": [],
        "audio": [],
        "state": None,
    }


def _runtime_session(interview_id: str) -> dict[str, Any]:
    session = interview_sessions.get(interview_id)
    if session is None:
        session = _empty_runtime_session()
        interview_sessions[interview_id] = session
    return session


def _append_bounded(session: dict[str, Any], key: str, value: Any, limit: int) -> None:
    items = session.setdefault(key, [])
    items.append(value)
    if len(items) > limit:
        del items[:-limit]


def interview_question_limit() -> int:
    return max(2, int(settings.max_questions_per_interview or 10))


def _question_signature(question: dict[str, Any]) -> str:
    return str(question.get("text") or "").strip().casefold()


def fetch_resume_for_user(resume_id: str, user_id: str) -> dict[str, Any] | None:
    result = (
        supabase.table("resumes")
        .select("id, user_id, file_name, parsed_json, raw_text")
        .eq("id", resume_id)
        .eq("user_id", user_id)
        .execute()
    )
    return result.data[0] if result.data else None


def verify_interview_access(interview_id: str, user_id: str) -> dict[str, Any]:
    result = (
        supabase.table("interviews")
        .select("id, user_id, resume_id, job_role, interview_mode, status, overall_score, created_at, completed_at")
        .eq("id", interview_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise LookupError("Interview not found")
    return result.data[0]


def list_interviews_for_user(user_id: str, limit: int = 20) -> list[dict[str, Any]]:
    result = (
        supabase.table("interviews")
        .select("id, resume_id, job_role, interview_mode, status, overall_score, created_at, completed_at")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data or []


def get_interview_status_payload(interview_id: str, user_id: str) -> dict[str, Any] | None:
    try:
        interview = verify_interview_access(interview_id, user_id)
    except LookupError:
        return None

    return {
        "interview": interview,
        "questions": load_persisted_questions(interview_id),
    }


def question_payload(question: dict[str, Any], order_idx: int | None = None) -> dict[str, Any]:
    resolved_order = question.get("order_idx")
    if not isinstance(resolved_order, int):
        resolved_order = order_idx if order_idx is not None else 0

    return {
        "text": str(question.get("text") or "").strip(),
        "category": question.get("category"),
        "topic": question.get("topic"),
        "difficulty": question.get("difficulty"),
        "why_asked": question.get("why_asked"),
        "is_weakness_focused": bool(question.get("is_weakness_focused", False)),
        "order_idx": resolved_order,
    }


def persist_question(
    interview_id: str,
    question: dict[str, Any],
) -> dict[str, Any]:
    payload = question_payload(question)
    if not payload["text"]:
        return question

    try:
        existing = (
            supabase.table("questions")
            .select("id")
            .eq("interview_id", interview_id)
            .eq("order_idx", payload["order_idx"])
            .limit(1)
            .execute()
        )
        if existing.data:
            return {
                **question,
                **payload,
                "id": existing.data[0].get("id"),
            }

        inserted = (
            supabase.table("questions")
            .insert({
                "interview_id": interview_id,
                **payload,
            })
            .execute()
        )
        if inserted.data:
            return {
                **question,
                **payload,
                "id": inserted.data[0].get("id"),
            }
    except Exception as e:
        logger.warning(
            "question_persist_failed",
            interview_id=interview_id,
            order_idx=payload["order_idx"],
            error=str(e),
        )

    return {
        **question,
        **payload,
    }


def find_persisted_question_id(
    interview_id: str,
    question: dict[str, Any],
) -> str | None:
    question_id = question.get("id")
    if question_id:
        return str(question_id)

    order_idx = question.get("order_idx")
    try:
        query = (
            supabase.table("questions")
            .select("id")
            .eq("interview_id", interview_id)
        )
        if isinstance(order_idx, int):
            query = query.eq("order_idx", order_idx)
        else:
            query = query.eq("text", str(question.get("text") or ""))

        result = query.limit(1).execute()
        if result.data:
            return result.data[0].get("id")
    except Exception as e:
        logger.warning(
            "question_lookup_failed",
            interview_id=interview_id,
            error=str(e),
        )

    return None


def persist_answer(
    interview_id: str,
    question: dict[str, Any],
    evaluation: dict[str, Any],
    duration_sec: float | None,
) -> None:
    question_id = find_persisted_question_id(interview_id, question)
    if not question_id:
        return

    try:
        supabase.table("answers").insert({
            "question_id": question_id,
            "answer_text": evaluation.get("transcript", ""),
            "score": evaluation.get("score"),
            "accuracy_score": evaluation.get("accuracy_score"),
            "clarity_score": evaluation.get("clarity_score"),
            "depth_score": evaluation.get("depth_score"),
            "cot_reasoning": evaluation.get("reasoning"),
            "audio_duration_sec": duration_sec,
        }).execute()
    except Exception as e:
        logger.warning(
            "answer_persist_failed",
            interview_id=interview_id,
            question_id=question_id,
            error=str(e),
        )


def load_persisted_questions(interview_id: str) -> list[dict[str, Any]]:
    result = (
        supabase.table("questions")
        .select("id, text, category, topic, difficulty, why_asked, is_weakness_focused, order_idx")
        .eq("interview_id", interview_id)
        .order("order_idx")
        .execute()
    )
    return result.data or []


def load_persisted_answers(question_ids: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not question_ids:
        return [], []

    result = (
        supabase.table("answers")
        .select("answer_text, score, accuracy_score, clarity_score, depth_score, cot_reasoning, created_at")
        .in_("question_id", question_ids)
        .order("created_at")
        .execute()
    )
    answers = []
    evaluations = []
    for row in result.data or []:
        answers.append({
            "transcript": row.get("answer_text") or "",
            "speech_score": row.get("score"),
        })
        evaluations.append({
            "score": row.get("score") or 0,
            "accuracy_score": row.get("accuracy_score") or 0,
            "clarity_score": row.get("clarity_score") or 0,
            "depth_score": row.get("depth_score") or 0,
            "cot_reasoning": row.get("cot_reasoning") or "",
        })

    return answers, evaluations


def load_answer_rows(question_ids: list[str]) -> list[dict[str, Any]]:
    if not question_ids:
        return []

    result = (
        supabase.table("answers")
        .select("question_id, answer_text, score, accuracy_score, clarity_score, depth_score, cot_reasoning, created_at")
        .in_("question_id", question_ids)
        .order("created_at")
        .execute()
    )
    return result.data or []


def _score_grade(score: int) -> str:
    if score >= 85:
        return "A"
    if score >= 70:
        return "B"
    if score >= 55:
        return "C"
    return "D"


def _readiness(score: int) -> str:
    if score >= 75:
        return "ready"
    if score >= 60:
        return "almost_ready"
    return "not_ready"


def build_report_payload(
    interview_id: str,
    overall_score: int | None,
    behavior_summary: dict | None,
) -> dict[str, Any]:
    questions = load_persisted_questions(interview_id)
    question_by_id = {
        str(question.get("id")): question
        for question in questions
        if question.get("id")
    }
    answers = load_answer_rows(list(question_by_id))
    scored_answers = [
        answer
        for answer in answers
        if isinstance(answer.get("score"), (int, float))
    ]

    if overall_score is None and scored_answers:
        overall_score = round(
            sum(float(answer.get("score") or 0) for answer in scored_answers)
            / len(scored_answers)
        )

    score = max(0, min(100, int(overall_score or 0)))
    topics: dict[str, list[dict[str, Any]]] = {}
    for answer in answers:
        question = question_by_id.get(str(answer.get("question_id")), {})
        topic = question.get("topic") or question.get("category") or "General"
        topics.setdefault(topic, []).append(answer)

    feedback_json = {}
    for topic, topic_answers in topics.items():
        topic_scores = [
            int(answer.get("score") or 0)
            for answer in topic_answers
            if isinstance(answer.get("score"), (int, float))
        ]
        average = round(sum(topic_scores) / len(topic_scores), 1) if topic_scores else 0
        feedback_json[topic] = {
            "average_score": average,
            "attempts": len(topic_answers),
            "feedback": topic_answers[-1].get("cot_reasoning") or "Review answer depth and clarity.",
        }

    weak_topics = [
        topic
        for topic, details in feedback_json.items()
        if details["average_score"] < settings.strong_score_threshold
    ][:3]
    strengths = [
        topic
        for topic, details in feedback_json.items()
        if details["average_score"] >= settings.strong_score_threshold
    ][:3]

    return {
        "interview_id": interview_id,
        "overall_score": score,
        "grade": _score_grade(score),
        "interview_readiness": _readiness(score),
        "feedback_json": feedback_json,
        "improvement_plan": [
            {
                "priority": index + 1,
                "topic": topic,
                "action": "Practice structured answers with a clear situation, decision, and result.",
                "resource": "Review the transcript and retry a focused mock question.",
                "estimated_time": "20 minutes",
                "why": "This topic scored below the readiness threshold.",
            }
            for index, topic in enumerate(weak_topics)
        ],
        "speech_summary": {
            "answers_count": len(answers),
            "behavior": behavior_summary or {},
        },
        "strengths": strengths or ["Completed the interview session"],
        "next_session_focus": weak_topics or ["Continue practicing with a more targeted role prompt"],
    }


def upsert_report(
    interview_id: str,
    overall_score: int | None,
    behavior_summary: dict | None,
) -> dict[str, Any] | None:
    payload = build_report_payload(
        interview_id=interview_id,
        overall_score=overall_score,
        behavior_summary=behavior_summary,
    )

    try:
        result = (
            supabase.table("reports")
            .upsert(payload, on_conflict="interview_id")
            .execute()
        )
        return result.data[0] if result.data else payload
    except Exception as e:
        logger.warning(
            "report_upsert_failed",
            interview_id=interview_id,
            error=str(e),
        )
        return None


def restore_session_state(
    interview_id: str,
    user_id: str,
    submitted_question: str,
) -> dict[str, Any] | None:
    interview = (
        supabase.table("interviews")
        .select("id, user_id, resume_id, job_role, interview_mode")
        .eq("id", interview_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not interview.data:
        return None

    interview_row = interview.data[0]
    resume_id = interview_row.get("resume_id")
    resume = fetch_resume_for_user(resume_id, user_id) if resume_id else None
    if not resume:
        return None

    questions = load_persisted_questions(interview_id)
    if not questions and submitted_question.strip():
        questions = [question_payload({
            "text": submitted_question,
            "category": "Interview",
            "topic": interview_row.get("job_role") or "General",
            "difficulty": "medium",
            "why_asked": "Restored from the submitted answer request.",
            "is_weakness_focused": False,
            "order_idx": 0,
        })]
        questions[0] = persist_question(interview_id, questions[0])

    answers, evaluations = load_persisted_answers([
        str(question.get("id"))
        for question in questions
        if question.get("id")
    ])

    return restore_interview_state(
        user_id=user_id,
        resume=resume,
        job_role=interview_row.get("job_role") or "General",
        job_description="",
        interview_mode=interview_row.get("interview_mode") or "faang",
        questions=questions,
        answers=answers,
        evaluations=evaluations,
    )


def record_vision_cost(
    interview_id: str,
    result: dict,
    latency_ms: int,
) -> dict | None:
    usage = result.pop("_usage", None)
    if not usage:
        return None

    tokens_in = int(usage.get("tokens_in") or 0)
    tokens_out = int(usage.get("tokens_out") or 0)
    model = usage.get("model") or "gemini-2.5-flash"
    cost_inr = estimate_gemini_cost_inr(
        model=model,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        input_modality="text_image_video",
    )

    return record_ai_cost(
        interview_id=interview_id,
        model=model,
        call_type="vision_frame",
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_inr=cost_inr,
        latency_ms=latency_ms,
    )


def create_interview_session(
    *,
    user_id: str,
    resume_id: str | None,
    job_role: str,
    job_description: str,
    interview_mode: str,
) -> dict[str, Any]:
    if interview_mode not in {"faang", "startup", "hr"}:
        raise ValueError("Invalid interview mode")

    if not resume_id:
        raise ValueError("Resume is required")

    resume = fetch_resume_for_user(resume_id, user_id)
    if not resume:
        raise LookupError("Resume not found")

    interview_id = str(uuid.uuid4())
    clean_job_role = job_role.strip() or "General"
    clean_job_description = job_description.strip()

    created = (
        supabase.table("interviews")
        .insert({
            "id": interview_id,
            "user_id": user_id,
            "resume_id": resume_id,
            "job_role": clean_job_role,
            "interview_mode": interview_mode,
            "status": "in_progress",
        })
        .execute()
    )

    agent_state, first_question, persona = create_interview_state(
        user_id=user_id,
        resume=resume,
        job_role=clean_job_role,
        job_description=clean_job_description,
        interview_mode=interview_mode,
    )
    first_question = persist_question(interview_id, first_question)
    if agent_state.get("questions"):
        agent_state["questions"][-1] = first_question

    session = _runtime_session(interview_id)
    session["frames"] = []
    session["audio"] = []
    session["state"] = agent_state

    return {
        "success": True,
        "interview_id": interview_id,
        "first_question": first_question,
        "persona_name": persona["name"],
        "opening_line": persona["opening_line"],
        "job_role": clean_job_role,
        "job_description": clean_job_description,
        "interview_mode": interview_mode,
        "resume_id": resume_id,
        "created_at": (
            created.data[0].get("created_at")
            if created.data
            else datetime.now(timezone.utc).isoformat()
        ),
    }


async def analyze_interview_frame(
    *,
    interview_id: str,
    user_id: str | None = None,
    frame_bytes: bytes,
    mime_type: str,
) -> dict[str, Any]:
    if user_id:
        verify_interview_access(interview_id, user_id)

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
    _append_bounded(
        _runtime_session(interview_id),
        "frames",
        result,
        MAX_SESSION_FRAMES,
    )

    return {
        "success": True,
        "analysis": result,
        "cost": cost_record,
        "session_cost": get_interview_cost_summary(interview_id),
    }


async def evaluate_audio_answer(
    *,
    interview_id: str,
    user_id: str,
    question: str,
    audio_bytes: bytes,
    mime_type: str,
    duration_sec: float | None,
) -> dict[str, Any]:
    verify_interview_access(interview_id, user_id)
    session = _runtime_session(interview_id)
    state = session.get("state")
    if not state:
        state = restore_session_state(
            interview_id=interview_id,
            user_id=user_id,
            submitted_question=question,
        )

    if not state:
        raise LookupError("Interview session not found")

    state = ensure_submitted_question(state, question)
    answered_question = persist_question(interview_id, state.get("questions", [])[-1])
    state["questions"][-1] = answered_question

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

    next_state, agent_evaluation, next_question = apply_answer_and_generate_next(
        state=state,
        speech_evaluation=result,
    )
    result = to_audio_evaluation(result, agent_evaluation)
    persist_answer(interview_id, answered_question, result, duration_sec)

    if next_question:
        next_question = persist_question(interview_id, next_question)
        if next_state.get("questions"):
            next_state["questions"][-1] = next_question
    elif len(next_state.get("questions", [])) < interview_question_limit():
        next_state, next_question = generate_next_question(next_state)
        next_question = persist_question(interview_id, next_question)
        if next_state.get("questions"):
            next_state["questions"][-1] = next_question

    session["state"] = next_state
    _append_bounded(
        session,
        "audio",
        result,
        MAX_SESSION_AUDIO_RESULTS,
    )

    return {
        "success": True,
        "evaluation": result,
        "next_question": next_question,
        "cost": cost_record,
        "session_cost": get_interview_cost_summary(interview_id),
    }


def get_behavior_summary_payload(
    interview_id: str,
    user_id: str | None = None,
) -> dict[str, Any]:
    if user_id:
        verify_interview_access(interview_id, user_id)

    summary = aggregate_behavior_analysis(_runtime_session(interview_id).get("frames", []))
    return {
        "success": True,
        "summary": summary,
        "session_cost": get_interview_cost_summary(interview_id),
    }


async def synthesize_question_audio(
    *,
    interview_id: str,
    user_id: str | None = None,
    text: str,
    request_id: str | None,
    voice_id: str | None,
) -> dict[str, Any]:
    if user_id:
        verify_interview_access(interview_id, user_id)

    started_at = time.perf_counter()
    speech = await synthesize_interviewer_speech(
        text=text,
        voice_id=voice_id,
    )
    latency_ms = round((time.perf_counter() - started_at) * 1000)
    speech["request_id"] = request_id
    speech["text"] = text

    if speech.get("success"):
        model = speech.get("model") or settings.elevenlabs_tts_model
        speech["cost"] = record_ai_cost(
            interview_id=interview_id,
            model=model,
            call_type="text_to_speech",
            cost_inr=estimate_elevenlabs_tts_cost_inr(
                model=model,
                text=text,
            ),
            latency_ms=latency_ms,
        )
        speech["session_cost"] = get_interview_cost_summary(interview_id)

    return speech


def complete_interview_session(
    *,
    interview_id: str,
    user_id: str,
    overall_score: int | None,
    behavior_summary: dict | None,
) -> dict[str, Any] | None:
    interview = (
        supabase.table("interviews")
        .select("id")
        .eq("id", interview_id)
        .eq("user_id", user_id)
        .execute()
    )

    if not interview.data:
        return None

    summary = get_interview_cost_summary(interview_id)
    report = upsert_report(
        interview_id=interview_id,
        overall_score=overall_score,
        behavior_summary=behavior_summary,
    )
    final_score = report.get("overall_score") if report else overall_score
    update_data = {
        "status": "completed",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "total_tokens": summary["total_tokens"],
    }

    if final_score is not None:
        update_data["overall_score"] = max(0, min(100, int(final_score)))

    if behavior_summary is not None:
        update_data["behavior_notes"] = [behavior_summary]

    supabase.table("interviews").update(update_data).eq("id", interview_id).execute()
    interview_sessions.pop(interview_id, None)

    return {
        "success": True,
        "interview_id": interview_id,
        "session_cost": summary,
    }


def _initial_state(
    *,
    user_id: str,
    resume: dict[str, Any],
    job_role: str,
    job_description: str,
    interview_mode: str,
) -> InterviewState:
    parsed_resume = resume.get("parsed_json") or {}
    if not isinstance(parsed_resume, dict):
        parsed_resume = {}

    return {
        "user_id": user_id,
        "resume_id": resume["id"],
        "job_role": job_role,
        "job_description": job_description,
        "resume_summary": parsed_resume,
        "difficulty": "medium",
        "interview_plan": [],
        "questions": [],
        "answers": [],
        "evaluations": [],
        "speech_metrics": [],
        "behavior_data": [],
        "current_index": 0,
        "weak_topics": [],
        "strong_topics": [],
        "session_topic_scores": {},
        "interview_mode": interview_mode,
        "difficulty_profile": "beginner",
        "retrieved_chunks": [],
        "report": None,
    }


def _merge_state(state: InterviewState, patch: dict[str, Any]) -> InterviewState:
    next_state = deepcopy(state)
    next_state.update(patch)
    return next_state


def _safe_retrieve(state: InterviewState) -> InterviewState:
    try:
        return _merge_state(state, retriever_agent(state))
    except Exception as e:
        logger.warning(
            "agent_retrieval_skipped",
            resume_id=state.get("resume_id"),
            error=str(e),
        )
        return _merge_state(state, {"retrieved_chunks": []})


def _safe_generate(state: InterviewState) -> tuple[InterviewState, dict[str, Any]]:
    questions = state.get("questions", [])
    try:
        next_state = _merge_state(state, generator_agent(state))
    except Exception as e:
        logger.exception(
            "agent_question_generation_failed",
            resume_id=state.get("resume_id"),
            error=str(e),
        )
        fallback = fallback_question_for_index(
            state,
            questions,
            "Fallback generated by the interview agent flow.",
        )
        next_state = _merge_state(state, {"questions": questions + [fallback]})

    question = next_state.get("questions", [])[-1]
    previous_question_texts = {
        _question_signature(existing_question)
        for existing_question in questions
        if _question_signature(existing_question)
    }
    if _question_signature(question) in previous_question_texts:
        fallback = fallback_question_for_index(
            state,
            questions,
            "Fallback replacement because the generated question repeated an earlier prompt.",
        )
        next_state = _merge_state(next_state, {"questions": questions + [fallback]})
        question = fallback

    return next_state, question


def generate_next_question(state: InterviewState) -> tuple[InterviewState, dict[str, Any]]:
    retrieved_state = _safe_retrieve(state)
    return _safe_generate(retrieved_state)


def create_interview_state(
    *,
    user_id: str,
    resume: dict[str, Any],
    job_role: str,
    job_description: str,
    interview_mode: str,
) -> tuple[InterviewState, dict[str, Any], dict[str, str]]:
    state = _initial_state(
        user_id=user_id,
        resume=resume,
        job_role=job_role,
        job_description=job_description,
        interview_mode=interview_mode,
    )

    try:
        state = _merge_state(state, planner_agent(state))
    except Exception as e:
        logger.exception(
            "agent_planning_failed",
            resume_id=resume.get("id"),
            error=str(e),
        )

    state, first_question = generate_next_question(state)
    persona = get_persona(interview_mode)
    return state, first_question, persona


def restore_interview_state(
    *,
    user_id: str,
    resume: dict[str, Any],
    job_role: str,
    job_description: str = "",
    interview_mode: str,
    questions: list[dict[str, Any]] | None = None,
    answers: list[dict[str, Any]] | None = None,
    evaluations: list[dict[str, Any]] | None = None,
) -> InterviewState:
    state = _initial_state(
        user_id=user_id,
        resume=resume,
        job_role=job_role,
        job_description=job_description,
        interview_mode=interview_mode,
    )
    questions = questions or []
    answers = answers or []
    evaluations = evaluations or []
    current_index = max(len(answers), len(questions) - 1 if questions else 0)

    return _merge_state(state, {
        "questions": questions,
        "answers": answers,
        "evaluations": evaluations,
        "current_index": min(current_index, interview_question_limit()),
    })


def ensure_submitted_question(
    state: InterviewState,
    question_text: str,
) -> InterviewState:
    clean_text = question_text.strip()
    if not clean_text:
        return state

    questions = state.get("questions", [])
    if questions and str(questions[-1].get("text") or "").strip() == clean_text:
        return state

    restored_question = {
        "text": clean_text,
        "category": "Interview",
        "topic": state.get("job_role", "General"),
        "difficulty": state.get("difficulty", "medium"),
        "why_asked": "Restored from the submitted answer request.",
        "is_weakness_focused": False,
        "order_idx": len(questions),
    }
    return _merge_state(state, {
        "questions": questions + [restored_question],
        "current_index": len(questions),
    })


def apply_answer_and_generate_next(
    state: InterviewState,
    speech_evaluation: dict[str, Any],
) -> tuple[InterviewState, dict[str, Any], dict[str, Any] | None]:
    transcript = speech_evaluation.get("transcript", "")
    answers = state.get("answers", []) + [{
        "transcript": transcript,
        "speech_score": speech_evaluation.get("score"),
        "provider": speech_evaluation.get("provider"),
        "model": speech_evaluation.get("model"),
    }]
    state = _merge_state(state, {"answers": answers})

    try:
        evaluation_patch = evaluator_agent(state)
        state = _merge_state(state, evaluation_patch)
        evaluation = state.get("evaluations", [])[-1]
    except Exception as e:
        logger.exception(
            "agent_evaluation_failed",
            resume_id=state.get("resume_id"),
            error=str(e),
        )
        evaluation = {
            "score": speech_evaluation.get("score", 0),
            "accuracy_score": speech_evaluation.get("accuracy_score", 0),
            "clarity_score": speech_evaluation.get("clarity_score", 0),
            "depth_score": speech_evaluation.get("depth_score", 0),
            "cot_reasoning": speech_evaluation.get("reasoning", "Speech evaluator fallback."),
        }
        state = _merge_state(state, {"evaluations": state.get("evaluations", []) + [evaluation]})

    next_index = state.get("current_index", 0) + 1
    state = _merge_state(state, {"current_index": next_index})

    if next_index >= interview_question_limit():
        return state, evaluation, None

    state, next_question = generate_next_question(state)
    return state, evaluation, next_question


def to_audio_evaluation(
    speech_evaluation: dict[str, Any],
    agent_evaluation: dict[str, Any],
) -> dict[str, Any]:
    return {
        **speech_evaluation,
        "score": agent_evaluation.get("score", speech_evaluation.get("score", 0)),
        "accuracy_score": agent_evaluation.get(
            "accuracy_score",
            speech_evaluation.get("accuracy_score", 0),
        ),
        "clarity_score": agent_evaluation.get(
            "clarity_score",
            speech_evaluation.get("clarity_score", 0),
        ),
        "depth_score": agent_evaluation.get(
            "depth_score",
            speech_evaluation.get("depth_score", 0),
        ),
        "reasoning": agent_evaluation.get(
            "cot_reasoning",
            speech_evaluation.get("reasoning", ""),
        ),
    }
