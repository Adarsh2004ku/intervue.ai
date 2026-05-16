from supabase import create_client,Client
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool
from backend.core.config import settings
from backend.core.logging import get_logger
from backend.services.cache.redis_client import (
    RedisClientProxy,
    check_redis_connection,
    get_redis_client,
)


logger = get_logger("db")


# Supabase client
def get_supabase_client()->Client:
    """ Crete and return a supabase client with a service role key"""
    return create_client(settings.supabase_url,settings.supabase_service_key)

supabase: Client = get_supabase_client()

# -- SQLALCHEMY ENGINE for connection pooling

def get_engine():
    """ 
    Create SQL Alchemyy engine with queuepool for connection management
    """
    if not settings.database_url:
        return None
    
    return create_engine(
        settings.database_url,
        poolclass= QueuePool,
        pool_size= 20,
        max_overflow= 10,
        pool_pre_ping=True,
        pool_recycle=300,
    )

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
