from google.genai import types
import google.genai as genai

from backend.core.config import settings
from backend.core.logging import get_logger

logger = get_logger("embedder")

# Let SDK choose correct API version automatically
_client = genai.Client(
    api_key=settings.google_api_key
)


def embed_query(text: str) -> list[float]:
    """Embed a single text string into a 768-dim vector."""

    model_name = settings.embedding_model.replace("models/", "")

    response = _client.models.embed_content(
        model=model_name,
        contents=[text],
        config=types.EmbedContentConfig(
            output_dimensionality=768
        )
    )

    return response.embeddings[0].values


def embed_texts(text: str) -> list[float]:
    """Backward-compatible alias for single-text embedding."""
    return embed_query(text)


def embed_text(texts: list[str]) -> list[list[float]]:
    """Embed multiple text strings into 768-dim vectors."""

    model_name = settings.embedding_model.replace("models/", "")

    response = _client.models.embed_content(
        model=model_name,
        contents=texts,
        config=types.EmbedContentConfig(
            output_dimensionality=768
        )
    )

    return [embedding.values for embedding in response.embeddings]
