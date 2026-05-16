import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException

from ai.agents.generator import question_payload
from backend.db.session import supabase


INTERVIEW_LIST_COLUMNS = (
    "id, resume_id, job_role, job_description, interview_mode, status, "
    "overall_score, created_at, completed_at"
)

INTERVIEW_LIST_COLUMNS_LEGACY = (
    "id, resume_id, job_role, interview_mode, status, "
    "overall_score, created_at, completed_at"
)

QUESTION_COLUMNS = (
    "id, text, category, topic, difficulty, why_asked, "
    "is_weakness_focused, order_idx, created_at"
)


def _missing_job_description_column(exc: Exception) -> bool:
    error_text = str(exc).lower()
    return "job_description" in error_text and (
        "schema cache" in error_text
        or "pgrst204" in error_text
        or "42703" in error_text
        or "column interviews.job_description does not exist" in error_text
    )


def _with_job_description_default(row: dict[str, Any]) -> dict[str, Any]:
    return {
        **row,
        "job_description": row.get("job_description") or "",
    }


def verify_resume_for_user(resume_id: str, user: dict) -> None:
    if not fetch_resume_for_user(resume_id, user):
        raise HTTPException(status_code=404, detail="Resume not found")


def fetch_resume_for_user(resume_id: str, user: dict) -> dict[str, Any] | None:
    resume = (
        supabase.table("resumes")
        .select("id, parsed_json, raw_text")
        .eq("id", resume_id)
        .eq("user_id", user["sub"])
        .execute()
    )
    return resume.data[0] if resume.data else None


def create_interview_record(
    *,
    interview_id: str,
    user_id: str,
    resume_id: str | None,
    job_role: str,
    job_description: str,
    interview_mode: str,
) -> dict[str, Any]:
    interview_payload = {
        "id": interview_id,
        "user_id": user_id,
        "resume_id": resume_id,
        "job_role": job_role,
        "job_description": job_description,
        "interview_mode": interview_mode,
        "status": "in_progress",
    }

    try:
        result = supabase.table("interviews").insert(interview_payload).execute()
    except Exception as exc:
        if not _missing_job_description_column(exc):
            raise

        legacy_payload = {
            key: value
            for key, value in interview_payload.items()
            if key != "job_description"
        }
        result = supabase.table("interviews").insert(legacy_payload).execute()

    row = result.data[0] if result.data else {}
    return {
        "id": row.get("id") or interview_id,
        "resume_id": row.get("resume_id") or resume_id,
        "job_role": row.get("job_role") or job_role,
        "job_description": row.get("job_description") or job_description,
        "interview_mode": row.get("interview_mode") or interview_mode,
        "created_at": row.get("created_at") or datetime.now(timezone.utc).isoformat(),
    }


def list_interviews_for_user(user: dict) -> list[dict[str, Any]]:
    try:
        result = (
            supabase.table("interviews")
            .select(INTERVIEW_LIST_COLUMNS)
            .eq("user_id", user["sub"])
            .order("created_at", desc=True)
            .execute()
        )
    except Exception as exc:
        if not _missing_job_description_column(exc):
            raise

        result = (
            supabase.table("interviews")
            .select(INTERVIEW_LIST_COLUMNS_LEGACY)
            .eq("user_id", user["sub"])
            .order("created_at", desc=True)
            .execute()
        )

    return [_with_job_description_default(row) for row in result.data or []]


def get_interview_for_user(interview_id: str, user: dict) -> dict[str, Any]:
    result = (
        supabase.table("interviews")
        .select("*")
        .eq("id", interview_id)
        .eq("user_id", user["sub"])
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Interview not found")
    return _with_job_description_default(result.data[0])


def fetch_questions_for_interview(interview_id: str) -> list[dict[str, Any]]:
    result = (
        supabase.table("questions")
        .select(QUESTION_COLUMNS)
        .eq("interview_id", interview_id)
        .order("order_idx")
        .execute()
    )
    return result.data or []


def insert_question(interview_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    row = {
        "id": str(uuid.uuid4()),
        "interview_id": interview_id,
        **payload,
    }
    result = supabase.table("questions").insert(row).execute()
    return result.data[0] if result.data else row


def next_question_order(interview_id: str) -> int:
    result = (
        supabase.table("questions")
        .select("order_idx")
        .eq("interview_id", interview_id)
        .order("order_idx", desc=True)
        .limit(1)
        .execute()
    )
    if not result.data:
        return 0
    return int(result.data[0].get("order_idx") or 0) + 1


def _find_question(
    interview_id: str,
    question_text: str,
    question_id: str | None = None,
) -> dict[str, Any] | None:
    query = (
        supabase.table("questions")
        .select("*")
        .eq("interview_id", interview_id)
    )
    if question_id:
        query = query.eq("id", question_id)
    else:
        query = query.eq("text", question_text)

    result = query.limit(1).execute()
    return result.data[0] if result.data else None


def ensure_question(
    interview_id: str,
    interview: dict[str, Any],
    question_text: str,
    question_id: str | None = None,
) -> dict[str, Any]:
    existing = _find_question(interview_id, question_text, question_id)
    if existing:
        return existing

    order_idx = next_question_order(interview_id)
    previous_questions = [question.get("text", "") for question in fetch_questions_for_interview(interview_id)]
    payload = question_payload(
        interview.get("interview_mode") or "faang",
        interview.get("job_role") or "General",
        order_idx,
        interview.get("job_description") or "",
        resume_context="",
        previous_questions=previous_questions,
    )
    payload["text"] = question_text
    return insert_question(interview_id, payload)


def insert_answer(answer_payload: dict[str, Any]) -> None:
    supabase.table("answers").insert(answer_payload).execute()


def complete_interview_record(interview_id: str, update_data: dict[str, Any]) -> None:
    supabase.table("interviews").update(update_data).eq("id", interview_id).execute()


def upsert_report(report_payload: dict[str, Any]) -> None:
    supabase.table("reports").upsert(
        report_payload,
        on_conflict="interview_id",
    ).execute()


def update_topic_score(user_id: str, topic: str, score: float) -> None:
    supabase.rpc(
        "upsert_topic_score",
        {
            "p_user_id": user_id,
            "p_topic": topic,
            "p_new_score": score,
        },
    ).execute()
