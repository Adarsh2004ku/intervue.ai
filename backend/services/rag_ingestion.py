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

def chunk_text(text :str ,chunk_size : int = 500,overlap : int = 50)->list[dict]:
    """
    Split text into overlapping chunks.
    Each chunk is a dict with 'text', 'start', 'end' fields.
    Tries to break at sentence boundaries.
    """

    chunks = []
    start = 0
    while start<len(text):
        if end < len(text):
            # Look for period, exclamation, or newline
            for sep in [". ", "! ", "? ", "\n"]:
                last_sep = text.rfind(sep, start, end)
                if last_sep > start:
                    end = last_sep + len(sep)
                    break
        
        chunk = text[start:end].strip()
        if chunk and len(chunk) > 20:  # Skip very short chunks
            chunks.append({"text": chunk, "start": start, "end": end})

        start = end - overlap
        if start >= len(text):
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
