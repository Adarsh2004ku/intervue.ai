from __future__ import annotations

from functools import lru_cache
from urllib.parse import urlparse

import redis

from backend.core.config import settings
from backend.core.logging import get_logger


logger = get_logger("redis")

VALID_REDIS_SCHEMES = {"redis", "rediss", "unix"}


class RedisUnavailableError(RuntimeError):
    """Raised when Redis is not configured or the configured URL is invalid."""


class RedisClientProxy:
    """Lazy Redis proxy for modules that import a module-level redis_client."""

    def _client(self) -> redis.Redis:
        client = get_redis_client()
        if client is None:
            raise RedisUnavailableError("Redis is not available; check REDIS_URL")
        return client

    def __getattr__(self, name: str):
        return getattr(self._client(), name)

    def ping(self) -> bool:
        return bool(self._client().ping())


def _redis_url_is_valid(url: str) -> bool:
    if not url:
        return False

    return urlparse(url).scheme in VALID_REDIS_SCHEMES


@lru_cache(maxsize=1)
def get_redis_client() -> redis.Redis | None:
    url = settings.redis_url.strip()
    if not _redis_url_is_valid(url):
        logger.error(
            "redis_url_invalid",
            allowed_schemes=sorted(VALID_REDIS_SCHEMES),
        )
        return None

    try:
        return redis.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            health_check_interval=30,
        )
    except ValueError as exc:
        logger.error(
            "redis_client_create_failed",
            error=str(exc),
        )
        return None


def check_redis_connection() -> str:
    client = get_redis_client()
    if client is None:
        return "error: Redis is not configured"

    try:
        client.ping()
        return "ok"
    except Exception as exc:
        return f"error: {str(exc)[:100]}"
