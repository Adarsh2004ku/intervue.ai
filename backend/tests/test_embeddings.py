"""Tests for Gemini embedding model selection helpers."""

from backend.services.embeddings import embedder


def test_legacy_text_embedding_model_maps_to_supported_gemini_model(monkeypatch):
    monkeypatch.setattr(embedder.settings, "embedding_model", "models/text-embedding-004")

    assert embedder.get_embedding_model_name() == "gemini-embedding-001"


def test_embedding_model_strips_models_prefix(monkeypatch):
    monkeypatch.setattr(embedder.settings, "embedding_model", "models/gemini-embedding-001")

    assert embedder.get_embedding_model_name() == "gemini-embedding-001"


def test_embedding_2_query_prefix():
    assert (
        embedder._prepare_text_for_model(
            "python backend resume",
            "gemini-embedding-2",
            "RETRIEVAL_QUERY",
        )
        == "task: search result | query: python backend resume"
    )


def test_embedding_2_document_prefix():
    assert (
        embedder._prepare_text_for_model(
            "built FastAPI services",
            "gemini-embedding-2",
            "RETRIEVAL_DOCUMENT",
        )
        == "title: none | text: built FastAPI services"
    )
