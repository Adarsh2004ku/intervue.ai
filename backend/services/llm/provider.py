from litellm import Router
from backend.core.config import settings
from backend.core.logging import get_logger


logger = get_logger("llm_provider")

_router : Router | None = None

def get_llm_router() -> Router:
    """
    Get or create the liteLLm Router.
    Routes requests to gemini first fall back to groq
    """
    global _router
    if _router is None:
        _router = Router(
            model_list=[
                {
                    "model_name": "fast-llm",
                    "litellm_params": {
                        "model": f"gemini/{settings.primary_llm}",
                        "api_key": settings.google_api_key,
                        "rpm": 15,  # Free tier: 15 req/min
                        "tpm": 1000000,
                    },
                },
                {
                    "model_name": "fast-llm",
                    "litellm_params": {
                        "model": "groq/llama3-70b-8192",
                        "api_key": settings.groq_api_key,
                        "rpm": 30,
                    },
                },
            ],
            routing_strategy="least-busy",
            num_retries=3,
            timeout=30,
            fallbacks=[{"fast-llm": ["groq/llama3-70b-8192"]}],
        )
        logger.info("llm_router_initialized")
    return _router

def get_gemini_direct():
    """
    Get a direct Gemini LLm instance for features that need 
    GEmni specific capabilities(audio,vision,structured output).
    """

    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(
        model = settings.primary_llm,
        google_api_key = settings.google_api_key,
        temperature = 0.3,
    )