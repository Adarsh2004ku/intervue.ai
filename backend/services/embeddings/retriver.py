import numpy as np
from backend.services.embeddings.embedder import embed_text
from backend.db.session import supabase
from backend.core.config import settings
from backend.core.logging import get_logger


logger = get_logger("retriver")
"""
RAG retrieval pipeline:
1. Embed the query using Gemini text-embedding-004
2. Search pgvector using cosine similarity
3. Apply MMR (Maximal Marginal Relevance) reranking
4. Return top-k non-redundant chunks
"""

def cosine_similarity(a:list[float],b:list[float])->float:
    """
    Compute cosine similarity between two vectors
    """

    a_np = np.array(a)
    b_np = np.array(b)
    norm_a = np.linalg.norm(a_np)
    norm_b = np.linalg.norm(b_np)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a_np,b_np)/(norm_a * norm_b))


def rerieve_chunks(resume_id : str,
    query:str,top_k : int = 5,
    section_filter : str |None = None,mmr_lambda : float = 0.7
    )->list[dict]:
    """
    Retrieve the most relevant chunks for a query using pgvector + MMR.
    
    mmr_lambda controls relevance vs diversity:
    - 1.0 = pure relevance (may return redundant chunks)
    - 0.0 = pure diversity (may return irrelevant chunks)
    - 0.7 = balanced (default)
    """
     

     # step 1 Embed the query 
    query_vector = embed_text(query)

    try:
        result = supabase.rpc(
            "match_chunks",
            {
                "p_resume_id": resume_id,
                "p_query_embedding": query_vector,
                "p_match_count": top_k * 2,  # Get more candidates for MMR
                "p_section_tag": section_filter,
            }
        ).execute()
        candidates = result.data if result.data else[]
    
    except Exception as e:
        logger.error("retrival_failed",error = str(e))
        return []
    
    if not candidates:
        return []
    

    # step 3 MMR rereanking

    selected = []
    while len(selected) < top_k and candidates:
        if not selected:
            # First chunk : pick the most relevant
            best = max(
                candidates,
                key = lambda c :c.get("similarity",0),
            )
        else:
            # Subsequent chunks: balance relevance and diversity
            def mmr_score(candidate):
                relevance = candidate.get("similarity",0),
                redundancy = max(
                    cosine_similarity(
                        candidate.get("embedding",[]),
                        s.get("embedding",[]),
                    )
                    for s in selected
                )
                return mmr_lambda * relevance - (1 - mmr_lambda) * redundancy
            best = max(candidates,key = mmr_score)
            selected.append(best)
            candidates.remove(best)

            logger.info("chunks_retrived",query = query[:50],count = len(selected),resume_id = resume_id)
            return selected
 
