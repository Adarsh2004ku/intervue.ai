from typing import Any

import httpx
from langchain_google_genai import ChatGoogleGenerativeAI

from backend.core.config import settings
from backend.core.logging import get_logger


logger = get_logger("llm_provider")


def _invoke_gemini(
    prompt: str,
    *,
    model: str,
    temperature: float,
    max_tokens: int | None,
    request_timeout: int,
) -> str:
    kwargs: dict[str, Any] = {
        "model": model,
        "api_key": settings.google_api_key,
        "temperature": temperature,
        "request_timeout": request_timeout,
    }
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens

    response = ChatGoogleGenerativeAI(**kwargs).invoke(prompt)
    return str(response.content)


def _invoke_groq(
    prompt: str,
    *,
    temperature: float,
    max_tokens: int | None,
    request_timeout: int,
) -> str:
    if not settings.groq_api_key:
        raise RuntimeError("GROQ_API_KEY is not configured")

    payload: dict[str, Any] = {
        "model": settings.groq_model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
    }
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens

    with httpx.Client(timeout=request_timeout) as client:
        response = client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.groq_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()

    data = response.json()
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("Groq returned no choices")
    return str(choices[0].get("message", {}).get("content") or "")


def invoke_llm_text(
    prompt: str,
    *,
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int | None = None,
    request_timeout: int = 20,
    purpose: str = "llm_call",
) -> str:
    model = model or settings.primary_llm

    try:
        return _invoke_gemini(
            prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            request_timeout=request_timeout,
        )
    except Exception as gemini_error:
        logger.warning(
            "gemini_failed_using_groq_fallback",
            purpose=purpose,
            model=model,
            error=str(gemini_error),
        )

    try:
        content = _invoke_groq(
            prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            request_timeout=request_timeout,
        )
        logger.info(
            "groq_fallback_succeeded",
            purpose=purpose,
            model=settings.groq_model,
        )
        return content
    except Exception as groq_error:
        logger.warning(
            "groq_fallback_failed",
            purpose=purpose,
            model=settings.groq_model,
            error=str(groq_error),
        )
        raise
