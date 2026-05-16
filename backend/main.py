"""
FastAPI application entry point.
"""

import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Vercel may build this app with backend/ as the project root. Keep the
# repository root importable so absolute imports like backend.core and ai work.
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fastapi import FastAPI
from backend.core.config import settings
from backend.core.middleware import setup_cors, log_requests
from backend.core.logging import setup_logging, get_logger
from backend.db.session import check_db_connection
from backend.api.v1.router import api_router

# --- CRITICAL FIX: Inject API keys into system environment ---
# LangChain/Gemini looks for these in os.environ, not just Pydantic Settings.
os.environ['GOOGLE_API_KEY'] = settings.google_api_key
os.environ['GROQ_API_KEY'] = settings.groq_api_key
os.environ['LANGCHAIN_TRACING_V2'] = str(settings.langchain_tracing_v2).lower()
os.environ['LANGSMITH_API_KEY'] = settings.langsmith_api_key
os.environ['LANGSMITH_PROJECT'] = settings.langsmith_project
# -------------------------------------------------------------

setup_logging()
logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info("server_starting", environment=settings.environment)
    db_status = check_db_connection()
    logger.info("db_health_check", **db_status)
    yield
    logger.info("server_shutting_down")


app = FastAPI(
    title="Intervue.AI API",
    version="1.0.0",
    description="Agentic AI Interview Platform — Real-time voice + video interviews",
    lifespan=lifespan,
)

# Middleware
setup_cors(app)
app.middleware("http")(log_requests)

# Routes
app.include_router(api_router, prefix="/api/v1")


@app.get("/")
async def root():
    """API landing endpoint for browser visits to the backend root."""
    return {
        "service": "Intervue.AI API",
        "status": "ok",
        "health": "/health",
        "api_health": "/api/v1/health",
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    db_status = check_db_connection()
    return {
        "status": "ok",
        "version": "1.0.0",
        "environment": settings.environment,
        "database": db_status,
    }
