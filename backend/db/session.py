import redis
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool
from supabase import Client, create_client

from backend.core.config import settings
from backend.core.logging import get_logger


logger = get_logger("db")


# Supabase client
def get_supabase_client() -> Client:
    """Create and return a Supabase client with the service role key."""
    return create_client(settings.supabase_url, settings.supabase_service_key)


supabase: Client = get_supabase_client()


def get_engine():
    """Create a SQLAlchemy engine with QueuePool when DATABASE_URL is set."""
    if not settings.database_url:
        return None

    return create_engine(
        settings.database_url,
        poolclass=QueuePool,
        pool_size=20,
        max_overflow=10,
        pool_pre_ping=True,
        pool_recycle=300,
    )


def get_redis_client() -> redis.Redis:
    """Create and return a Redis client."""
    return redis.from_url(settings.redis_url, decode_responses=True)


redis_client: redis.Redis = get_redis_client()


def check_db_connection() -> dict:
    """Health check: verify Supabase and Redis are reachable."""
    status = {"supabase": "ok", "redis": "ok"}
    try:
        supabase.table("users").select("id").limit(1).execute()
    except Exception as e:
        status["supabase"] = f"error: {str(e)[:100]}"

    try:
        redis_client.ping()
    except Exception as e:
        status["redis"] = f"error: {str(e)[:100]}"
    return status
