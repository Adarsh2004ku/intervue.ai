from __future__ import annotations

from typing import Any, Callable

from celery import Task

from backend.core.config import settings
from backend.core.logging import get_logger


logger = get_logger("task_queue")


def queue_or_run_inline(
    *,
    task: Task,
    inline: Callable[[], Any],
    args: list[Any] | None = None,
    kwargs: dict[str, Any] | None = None,
    description: str,
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
