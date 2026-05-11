"""
Central configuration using Pydantic BaseSettings.
Uses pathlib to guarantee the .env file is always found, 
no matter what folder you run uvicorn from.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List
from pathlib import Path

# Calculate the absolute path to the backend/.env file
# config.py is in backend/core/, so we go up one level to backend/
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE_PATH = BASE_DIR / ".env"


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
    embedding_model: str = "gemini-embedding-001"  
    embedding_dimension: int = 768

    # Interview Config
    max_questions_per_interview: int = 10
    max_tokens_per_interview: int = 50000
    weak_score_threshold: int = 60
    strong_score_threshold: int = 75

    @property
    def cors_origin_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE_PATH),  # Uses absolute path!
        env_file_encoding="utf-8",
        extra="ignore"
    )

# Singleton — import this everywhere
settings = Settings()
