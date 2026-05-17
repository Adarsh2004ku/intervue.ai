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
    """
    Application settings loaded from environment variables.
    
    Configuration priority:
    1. Environment variables
    2. .env file in backend/ directory
    3. Default values
    """
    
    # =====================================================
    # LLM PROVIDERS (REQUIRED)
    # =====================================================
    google_api_key: str
    """Google Gemini API key - get from https://aistudio.google.com/apikey"""
    
    groq_api_key: str = ""
    """Groq API key - optional fallback provider"""

    groq_model: str = "llama-3.3-70b-versatile"
    """Groq OpenAI-compatible model used when Gemini fails"""

    gemini_cooldown_seconds: int = 300
    """Seconds to use Groq first after Gemini quota or rate-limit errors"""

    elevenlabs_api_key: str = ""
    """ElevenLabs API key - used for speech-to-text transcription"""

    elevenlabs_stt_model: str = "scribe_v2"
    """ElevenLabs speech-to-text model"""

    elevenlabs_voice_id: str = "Qdoacjdd3OKJ1mMc318A"
    """ElevenLabs voice ID used for interviewer speech"""

    elevenlabs_tts_model: str = "eleven_flash_v2_5"
    """ElevenLabs text-to-speech model"""

    elevenlabs_output_format: str = "mp3_44100_128"
    """ElevenLabs generated speech output format"""

    # =====================================================
    # LANGSMITH (Optional - for AI observability)
    # =====================================================
    langchain_tracing_v2: bool = False
    """Enable LangSmith tracing for debugging"""
    
    langsmith_api_key: str = ""
    """LangSmith API key - get from https://smith.langchain.com"""
    
    langsmith_project: str = "intervue-ai"
    """LangSmith project name"""

    # =====================================================
    # SUPABASE (REQUIRED - Database & Auth)
    # =====================================================
    supabase_url: str
    """Supabase project URL"""
    
    supabase_key: str
    """Supabase anonymous key"""
    
    supabase_service_key: str
    """Supabase service role key (keep secret)"""
    
    database_url: str = ""
    """PostgreSQL connection string (optional direct access)"""

    # =====================================================
    # REDIS (for task queue & caching)
    # =====================================================
    redis_url: str = "redis://localhost:6379/0"
    """Redis connection URL for Celery and caching"""

    redis_session_ttl_seconds: int = 86400
    """How long interview session state stays in Redis."""

    celery_enabled: bool = False
    """Queue non-critical background work through Celery when true."""

    celery_broker_url: str = ""
    """Celery broker URL. Defaults to redis_url when empty."""

    celery_result_backend: str = ""
    """Celery result backend URL. Defaults to redis_url when empty."""

    celery_task_always_eager: bool = False
    """Run Celery tasks inline, useful for local tests and debugging."""

    celery_result_expires_seconds: int = 3600
    """How long Celery stores task results."""

    # =====================================================
    # JWT AUTHENTICATION
    # =====================================================
    jwt_secret: str
    """Secret key for JWT signing"""
    
    jwt_algorithm: str = "HS256"
    """JWT algorithm (HS256 is standard)"""
    
    jwt_expiry_minutes: int = 10080  # 7 days
    """JWT token expiry duration"""

    # =====================================================
    # APPLICATION CONFIGURATION
    # =====================================================
    environment: str = "development"
    """Environment: development, staging, production"""
    
    frontend_url: str = "http://localhost:3000"
    """Frontend application URL (used for OAuth redirects)"""
    
    cors_origins: str = "http://localhost:3000"
    """Comma-separated list of allowed CORS origins"""
    
    log_level: str = "INFO"
    """Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL"""

    admin_emails: str = ""
    """Comma-separated email allowlist for admin-only routes."""

    # =====================================================
    # LLM MODEL CONFIGURATION
    # =====================================================
    primary_llm: str = "gemini-2.5-flash"
    """Primary LLM for interview generation"""
    
    embedding_model: str = "gemini-embedding-001"
    """Embedding model for resume parsing."""
    
    embedding_dimension: int = 768
    """Vector dimension for embeddings"""

    # =====================================================
    # INTERVIEW CONFIGURATION
    # =====================================================
    max_questions_per_interview: int = 10
    """Maximum questions per interview"""
    
    max_tokens_per_interview: int = 50000
    """Max tokens allowed per interview (cost control)"""

    api_cost_usd_to_inr: float = 83.0
    """USD to INR rate used for API cost estimates"""
    
    weak_score_threshold: int = 60
    """Score threshold for weak areas (0-100)"""
    
    strong_score_threshold: int = 75
    """Score threshold for strong areas (0-100)"""

    @property
    def cors_origin_list(self) -> List[str]:
        """Parse comma-separated CORS origins into a list."""
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @property
    def admin_email_list(self) -> List[str]:
        """Parse comma-separated admin emails into a normalized list."""
        return [
            email.strip().lower()
            for email in self.admin_emails.split(",")
            if email.strip()
        ]

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE_PATH),  # Uses absolute path!
        env_file_encoding="utf-8",
        extra="ignore"
    )

# Singleton — import this everywhere
settings = Settings()
