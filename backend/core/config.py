"""
Central configuration using Pydantic BaseSettings.
All environment variables are loaded and validated here.
No other file should read os.getenv() directly.
"""

from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # LLM Providers
    google_api_key: str
    groq_api_key: str = ""

    # LangSmith
    langchain_tracing_v2: bool = True
    langsmith_api_key: str = ""
    langsmith_project: str = "intervue-ai"

    # Supabase
    supabase_url: str
    supabase_key: str
    supabase_service_key: str
    database_url: str = ""

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Auth
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expiry_minutes: int = 10080  # 7 days

    # App
    environment: str = "development"
    frontend_url: str = "http://localhost:3000"
    cors_origins: str = "http://localhost:3000"

    # LLM Config
    primary_llm: str = "gemini-2.5-flash"
    embedding_model: str = "models/text-embedding-004"
    embedding_dimension: int = 768

    # Interview Config
    max_questions_per_interview: int = 10
    max_tokens_per_interview: int = 50000
    weak_score_threshold: int = 60
    strong_score_threshold: int = 75

    @property
    def cors_origin_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


# Singleton — import this everywhere
settings = Settings()