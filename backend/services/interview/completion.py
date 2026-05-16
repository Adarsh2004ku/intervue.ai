from datetime import datetime, timezone

from backend.core.logging import get_logger
from backend.services.cost_tracking import get_interview_cost_summary
from backend.services.interview.repository import (
    complete_interview_record,
    get_interview_for_user,
    update_topic_score,
    upsert_report,
)
from backend.services.interview.session_state import with_session_interview_context
from backend.services.reports import build_report_payload
from backend.services.cache.task_queue import queue_or_run_inline
from backend.services.cache.tasks import update_topic_scores_task


logger = get_logger("interview_completion")


def _topic_score_payload(report_payload: dict) -> list[dict]:
    topics = []
    for topic, details in (report_payload.get("feedback_json") or {}).items():
        score = details.get("score") if isinstance(details, dict) else None
        if score is None:
            continue
        topics.append({
            "topic": topic,
            "score": float(score),
        })
    return topics


def _update_topic_scores_inline(
    *,
    user_id: str,
    interview_id: str,
    topic_scores: list[dict],
) -> dict:
    updated = 0
    skipped = 0
    for item in topic_scores:
        topic = item.get("topic")
        score = item.get("score")
        if not topic or score is None:
            skipped += 1
            continue
        try:
            update_topic_score(user_id, str(topic), float(score))
            updated += 1
        except Exception as topic_error:
            logger.warning(
                "topic_score_update_failed",
                interview_id=interview_id,
                topic=topic,
                error=str(topic_error),
            )
            skipped += 1
    return {
        "interview_id": interview_id,
        "updated": updated,
        "skipped": skipped,
    }


def complete_interview_for_user(
    *,
    interview_id: str,
    user: dict,
    overall_score: int | None,
    behavior_summary: dict | None,
) -> dict:
    interview = with_session_interview_context(
        interview_id,
        get_interview_for_user(interview_id, user),
    )
    summary = get_interview_cost_summary(interview_id)
    update_data = {
        "status": "completed",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "total_tokens": summary["total_tokens"],
    }

    if overall_score is not None:
        update_data["overall_score"] = max(0, min(100, overall_score))

    if behavior_summary is not None:
        update_data["behavior_notes"] = [behavior_summary]

    complete_interview_record(interview_id, update_data)
    report_payload = build_report_payload(
        interview=interview,
        requested_score=update_data.get("overall_score"),
        behavior_summary=behavior_summary,
    )
    upsert_report(report_payload)

    topic_scores = _topic_score_payload(report_payload)
    topic_score_task = queue_or_run_inline(
        task=update_topic_scores_task,
        inline=lambda: _update_topic_scores_inline(
            user_id=user["sub"],
            interview_id=interview_id,
            topic_scores=topic_scores,
        ),
        args=[user["sub"], interview_id, topic_scores],
        description="topic score updates",
    )

    return {
        "success": True,
        "interview_id": interview_id,
        "session_cost": summary,
        "topic_score_status": topic_score_task["status"],
        "topic_score_task_id": topic_score_task["task_id"],
    }
