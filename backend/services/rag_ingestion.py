import hashlib

from backend.services.embeddings.embedder import embed_text
from backend.db.session import supabase
from backend.core.logging import get_logger


logger = get_logger("rag_ingestion")


def chunk_text(
    text: str,
    chunk_size: int = 500,
    overlap: int = 50,
) -> list[dict]:
    """
    Split text into overlapping chunks.
    """

    if not text:
        return []

    chunks = []
    start = 0
    text_len = len(text)

    while start < text_len:

        end = min(start + chunk_size, text_len)

        # Try sentence-aware chunking
        if end < text_len:

            last_sep = -1

            for sep in [". ", "! ", "? ", "\n"]:

                pos = text.rfind(sep, start, end)

                if pos > last_sep:
                    last_sep = pos

            if last_sep > start:
                end = last_sep + 2

        chunk = text[start:end].strip()

        if chunk and len(chunk) > 20:
            chunks.append(
                {
                    "text": chunk,
                    "start": start,
                    "end": end,
                }
            )

        if end >= text_len:
            break

        start = end - overlap

    return chunks


def embed_and_store(
    resume_id: str,
    chunks: list[dict],
    section_tags: list[str] | None = None,
) -> int:
    """
    Embed chunks and store in Supabase pgvector table.
    """

    if not chunks:
        return 0

    if section_tags is None:
        section_tags = ["general"] * len(chunks)

    texts = [c["text"] for c in chunks]

    logger.info(
        "embedding_chunks",
        count=len(texts),
        resume_id=resume_id,
    )

    # Batch embeddings
    vectors = embed_text(texts, task_type="RETRIEVAL_DOCUMENT")

    rows = []

    for chunk, vector, tag in zip(chunks, vectors, section_tags):

        sha = hashlib.sha256(
            chunk["text"].encode()
        ).hexdigest()

        rows.append(
            {
                "resume_id": resume_id,
                "chunk_text": chunk["text"],
                "section_tag": tag,
                "embedding": vector,
                "sha256_hash": sha,
            }
        )

    # Single batch upsert
    result = (
        supabase
        .table("resume_chunks")
        .upsert(
            rows,
            on_conflict="sha256_hash",
        )
        .execute()
    )

    stored = len(result.data) if result.data else 0

    logger.info(
        "chunks_stored",
        stored=stored,
        resume_id=resume_id,
    )

    return stored
