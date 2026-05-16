from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from celery import Celery

from backend.core.config import settings


def _with_required_ssl_cert_reqs(url: str) -> str:
    """Celery expects ssl_cert_reqs on rediss:// Redis URLs."""
    if not url.startswith("rediss://"):
        return url

    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query.setdefault("ssl_cert_reqs", "required")
    return urlunsplit((
        parts.scheme,
        parts.netloc,
        parts.path,
        urlencode(query),
        parts.fragment,
    ))


def _celery_url(value: str) -> str:
    return _with_required_ssl_cert_reqs((value or settings.redis_url).strip())


celery_app = Celery(
    "intervue_ai",
    broker=_celery_url(settings.celery_broker_url),
    backend=_celery_url(settings.celery_result_backend),
    include=[
        "backend.services.cache.tasks",
    ],
)

celery_app.conf.update(
    accept_content=["json"],
    task_serializer="json",
    result_serializer="json",
    result_expires=settings.celery_result_expires_seconds,
    task_track_started=True,
    task_always_eager=settings.celery_task_always_eager,
    task_eager_propagates=True,
    timezone="UTC",
)
