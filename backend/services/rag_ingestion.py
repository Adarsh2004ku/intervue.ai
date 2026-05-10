import hashlib
from backend.services.embeddings.embedder import embed_text
from backend.db.session import supabase
from backend.core.logging import get_logger
"""
RAG ingestion pipeline:
1. Chunk text into 500-char segments with 50-char overlap
2. Embed each chunk using Gemini text-embedding-004
3. Upsert into resume_chunks table in Supabase with SHA-256 dedup
"""

logger = get_logger("rag_ingestio")

def chunk_text(
    text: str, chunk_size: int = 500, overlap: int = 50
) -> list[dict]:
    """
    Split text into overlapping chunks.
    Tries to break at sentence boundaries (., !, ?, \n).
    """
    if not text:
        return []

    chunks = []
    start = 0

    while start < len(text):
        # Determine the end of the current chunk
        end = start + chunk_size

        # If we haven't reached the end of the text, try to find a sentence break
        if end >= len(text):
            end = len(text)
        else:
            # Look for the last sentence separator within the chunk
            last_sep = -1
            for sep in [". ", "! ", "? ", "\n"]:
                pos = text.rfind(sep, start, end)
                if pos > last_sep:
                    last_sep = pos
            
            # If we found a separator, break there; otherwise hard-break at chunk_size
            if last_sep > start:
                end = last_sep + 2  # Include the separator
            else:
                end = chunk_size

        chunk = text[start:end].strip()
        
        if chunk and len(chunk) > 20:  # Skip tiny fragments
            chunks.append({"text": chunk, "start": start, "end": end})

        # Move the start pointer forward, minus the overlap
        start = end - overlap
        
        # Safety: ensure start always moves forward to prevent infinite loops
        if start <= 0 or end == len(text):
            break

    return chunks


def embed_and_store(
        resume_id:str,chunks : list[dict],
        section_tags : list[str] | None = None,)->int:
    """
    Embed chunks and store them in pgvector.
    Returns the number of chunks stored.
    Uses SHA-256 dedup to avoid re-embedding identical chunks.
    """ 
    if not chunks:
        return 0
   
    if section_tags is None :
        section_tags = ["general"] * len(chunks)
    
    texts = [c["text"] for c in chunks]
    logger.info('embedding_chunks',count = len(texts),resume_id = resume_id)

    # embed all chunks in batch
    vectors = embed_text(texts)
    # builds rows for upset

    rows = []
    for chunk ,vector,tag in zip(chunks,vectors,section_tags):
        sha = hashlib.sha256(chunk['text'].encode()).hexidigest()
        rows.append(
            {
                "resume_id": resume_id,
                "chunk_text" : chunk['text'],
                "section_tag" : tag,
                "embedding" : vector,
                "sha256_hash" : sha,
            }
        )

        
        result = supabase.table("resume_chunks").upsert(
            rows,on_conflict="sha256_hash"
        ).execute()

        stored = len(result.data) if result.data else 0
        logger.info("chunnks_stored",stored = stored,resume_id = resume_id)

        return stored
