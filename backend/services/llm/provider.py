from litellm import Router
import json
from typing import Any

from backend.core.config import settings
from backend.core.logging import get_logger


logger = get_logger("llm_provider")

_router : Router | None = None


def strip_json_fence(content: str) -> str:
    """Remove common markdown fences from model JSON output."""
    cleaned = content.strip()
    if not cleaned.startswith("```"):
        return cleaned

    parts = cleaned.split("```")
    if len(parts) < 2:
        return cleaned

    cleaned = parts[1].strip()
    if cleaned.startswith("json"):
        cleaned = cleaned[4:].strip()
    return cleaned


def parse_llm_json(content: str) -> dict[str, Any]:
    """Parse a JSON object returned by an LLM."""
    parsed = json.loads(strip_json_fence(content))
    if not isinstance(parsed, dict):
        raise ValueError("Expected a JSON object from LLM response")
    return parsed

def get_llm_router() -> Router:
    """
    Get or create the liteLLm Router.
    Routes requests to gemini first fall back to groq
    """
    global _router
    if _router is None:
        model_list = [
            {
                "model_name": "fast-llm",
                "litellm_params": {
                    "model": f"gemini/{settings.primary_llm}",
                    "api_key": settings.google_api_key,
                    "rpm": 15,
                    "tpm": 1000000,
                },
            }
        ]
        fallbacks = []

        if settings.groq_api_key:
            model_list.append(
                {
                    "model_name": "fast-llm-fallback",
                    "litellm_params": {
                        "model": "groq/llama3-70b-8192",
                        "api_key": settings.groq_api_key,
                        "rpm": 30,
                    },
                }
            )
            fallbacks = [{"fast-llm": ["fast-llm-fallback"]}]

        _router = Router(
            model_list=model_list,
            routing_strategy="least-busy",
            num_retries=3,
            timeout=30,
            fallbacks=fallbacks,
        )
        logger.info("llm_router_initialized")
    return _router

def get_gemini_direct(temperature: float = 0.3):
    """
    Get a direct Gemini LLm instance for features that need 
    GEmni specific capabilities(audio,vision,structured output).
    """

    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(
        model = settings.primary_llm,
        google_api_key = settings.google_api_key,
        temperature = temperature,
    )
