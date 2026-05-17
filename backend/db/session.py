from supabase import create_client,Client
from backend.core.config import settings
from backend.core.logging import get_logger
from backend.services.cache.redis_client import (
    RedisClientProxy,
    check_redis_connection,
)


logger = get_logger("db")


# Supabase client
def get_supabase_client()->Client:
    """ Crete and return a supabase client with a service role key"""
    return create_client(settings.supabase_url,settings.supabase_service_key)

supabase: Client = get_supabase_client()

# Redis Client
redis_client = RedisClientProxy()

def check_db_connection() -> dict:
    """
    Health check: verify Supabase and redis are reachable
    """
    status = {"supabase":"ok","redis":"ok"}
    try:
        supabase.table("users").select("id").limit(1).execute()
    except Exception as e:
            status["supabase"] = f"error: {str(e)[:100]}"

    status["redis"] = check_redis_connection()
    return status
