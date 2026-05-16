from __future__ import annotations

from typing import Any

from backend.core.logging import get_logger
from backend.services.cache.celery_app import celery_app
from backend.services.interview.repository import update_topic_score
from backend.services.rag_ingestion import embed_and_store


logger = get_logger("cache_tasks")


@celery_app.task(
    name="backend.services.cache.tasks.embed_resume_chunks",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def embed_resume_chunks_task(
    resume_id: str,
    chunks: list[dict[str, Any]],
    section_tags: list[str],
) -> dict[str, Any]:
    stored = embed_and_store(resume_id, chunks, section_tags)
    logger.info(
        "resume_embedding_task_completed",
        resume_id=resume_id,
        chunks_stored=stored,
    )
    return {
        "resume_id": resume_id,
        "chunks_stored": stored,
    }


@celery_app.task(
    name="backend.services.cache.tasks.update_topic_scores",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def update_topic_scores_task(
    user_id: str,
    interview_id: str,
    topic_scores: list[dict[str, Any]],
) -> dict[str, Any]:
    updated = 0
    skipped = 0

    for item in topic_scores:
        topic = item.get("topic")
        score = item.get("score")
        if not topic or score is None:
            skipped += 1
            continue

        update_topic_score(user_id, str(topic), float(score))
        updated += 1

    logger.info(
        "topic_scores_task_completed",
        interview_id=interview_id,
        updated=updated,
        skipped=skipped,
    )
    return {
        "interview_id": interview_id,
        "updated": updated,
        "skipped": skipped,
    }
