from __future__ import annotations

from typing import Any, Callable

from celery import Task

from backend.core.config import settings
from backend.core.logging import get_logger
from backend.services.cache.celery_app import celery_app


logger = get_logger("task_queue")


def queue_or_run_inline(
    *,
    task: Task,
    inline: Callable[[], Any],
    args: list[Any] | None = None,
    kwargs: dict[str, Any] | None = None,
    description: str,
    fallback_inline: bool = True,
) -> dict[str, Any]:
    """Queue a Celery task when enabled, otherwise run the same work inline."""
    if not settings.celery_enabled or settings.celery_task_always_eager:
        result = inline()
        return {
            "status": "completed",
            "result": result,
            "task_id": None,
        }

    try:
        async_result = task.apply_async(
            args=args or [],
            kwargs=kwargs or {},
        )
        logger.info(
            "task_queued",
            task_id=async_result.id,
            description=description,
        )
        return {
            "status": "queued",
            "result": None,
            "task_id": async_result.id,
        }
    except Exception as exc:
        if not fallback_inline:
            logger.warning(
                "task_queue_failed",
                description=description,
                error=str(exc),
            )
            return {
                "status": "failed",
                "result": None,
                "task_id": None,
                "queue_error": str(exc),
            }

        logger.warning(
            "task_queue_failed_running_inline",
            description=description,
            error=str(exc),
        )
        result = inline()
        return {
            "status": "completed",
            "result": result,
            "task_id": None,
            "queue_error": str(exc),
        }


def get_celery_task_status(task_id: str) -> dict[str, Any]:
    """Return normalized status for a Celery task id."""
    task_result = celery_app.AsyncResult(task_id)
    state = str(task_result.state or "PENDING").lower()
    payload: dict[str, Any] = {
        "task_id": task_id,
        "status": state,
        "ready": task_result.ready(),
        "successful": task_result.successful(),
        "failed": task_result.failed(),
    }

    if task_result.successful():
        payload["result"] = task_result.result
    elif task_result.failed():
        payload["error"] = str(task_result.result)

    return payload
