from langchain_google_genai import GoogleGenerativeAIEmbeddings
from backend.core.config import settings
from backend.core.logging import get_logger

logger = get_logger("embedder")

_embedings_model : GoogleGenerativeAIEmbeddings | None = None

def get_embeddings_model()-> GoogleGenerativeAIEmbeddings:
    """ Lazy Load the embeddings model singleton """
    global _embedings_model
    if _embedings_model is None:
        _embedings_model = GoogleGenerativeAIEmbeddings(
            model = settings.embedding_model
        )
    return _embedings_model

def embed_texts(text :str) -> list[float]:
    """ Embed a single text string into a 768-dim vector ."""
    model = get_embeddings_model()
    return model.embed_query(text)

def embed_texts(texts:list[str]) -> list[list[float]]:
    """ Embed multiple text strings into 768-dim vectors """
    model = get_embeddings_model()
    return model.embed_documents(texts)
