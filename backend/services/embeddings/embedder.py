from typing import Any

from backend.core.config import settings
from backend.core.logging import get_logger

logger = get_logger("embedder")

_client = None

_LEGACY_MODEL_ALIASES = {
    "models/text-embedding-004": "gemini-embedding-001",
    "text-embedding-004": "gemini-embedding-001",
    "models/embedding-001": "gemini-embedding-001",
    "embedding-001": "gemini-embedding-001",
}


def _google_genai() -> tuple[Any, Any]:
    import google.genai as genai
    from google.genai import types

    return genai, types


def _get_client():
    global _client
    if _client is None:
        genai, _ = _google_genai()
        _client = genai.Client(api_key=settings.google_api_key)
    return _client


def get_embedding_model_name() -> str:
    """Return the Gemini model id supported by the current embedContent API."""
    configured = (settings.embedding_model or "").strip()
    if not configured:
        return "gemini-embedding-001"

    model_key = configured.lower()
    if model_key in _LEGACY_MODEL_ALIASES:
        return _LEGACY_MODEL_ALIASES[model_key]

    if model_key.startswith("models/"):
        return configured[len("models/"):]

    return configured


def _prepare_text_for_model(text: str, model_name: str, task_type: str | None) -> str:
    if model_name != "gemini-embedding-2" or not task_type:
        return text

    if task_type == "RETRIEVAL_QUERY":
        return f"task: search result | query: {text}"
    if task_type == "RETRIEVAL_DOCUMENT":
        return f"title: none | text: {text}"
    return text


def _embedding_contents(texts: list[str], model_name: str):
    if model_name != "gemini-embedding-2" or len(texts) <= 1:
        return texts

    _, types = _google_genai()
    return [
        types.Content(parts=[types.Part.from_text(text=text)])
        for text in texts
    ]


def _embedding_config(model_name: str, task_type: str | None):
    _, types = _google_genai()
    config = {
        "output_dimensionality": settings.embedding_dimension,
    }
    if model_name == "gemini-embedding-001" and task_type:
        config["task_type"] = task_type
    return types.EmbedContentConfig(**config)


def embed_texts(text: str, task_type: str | None = None) -> list[float]:
    """Embed a single text string into a 768-dim vector."""
    model_name = get_embedding_model_name()
    prepared_text = _prepare_text_for_model(text, model_name, task_type)

    response = _get_client().models.embed_content(
        model=model_name,
        contents=[prepared_text],
        config=_embedding_config(model_name, task_type),
    )

    return response.embeddings[0].values


def embed_text(texts: list[str], task_type: str | None = None) -> list[list[float]]:
    """Embed multiple text strings into 768-dim vectors."""
    if not texts:
        return []

    model_name = get_embedding_model_name()
    prepared_texts = [
        _prepare_text_for_model(text, model_name, task_type)
        for text in texts
    ]

    response = _get_client().models.embed_content(
        model=model_name,
        contents=_embedding_contents(prepared_texts, model_name),
        config=_embedding_config(model_name, task_type),
    )

    vectors = [embedding.values for embedding in response.embeddings]
    if len(vectors) != len(texts):
        raise RuntimeError(
            f"Embedding model returned {len(vectors)} vectors for {len(texts)} inputs"
        )

    return vectors
