"""
Retriever Agent — fetches relevant resume chunks from pgvector
for the current question topic.
Uses cosine similarity + MMR reranking for diverse context.
"""

from backend.services.embeddings.retriever import retrieve_chunks  
from ai.agents.state import InterviewState
from backend.core.logging import get_logger

logger = get_logger("retriever_agent")


def retriever_agent(state: InterviewState) -> dict:
    """
    Retrieve relevant resume chunks for the current question topic.
    Returns updated state with 'retrieved_chunks' populated.
    """
    resume_id = state.get("resume_id", "")
    current_index = state.get("current_index", 0)
    interview_plan = state.get("interview_plan", [])

    # Determine current topic from interview plan
    if current_index < len(interview_plan):
        current_plan = interview_plan[current_index]
        query = f"{current_plan.get('category', '')} {current_plan.get('topic', '')} {current_plan.get('focus', '')}"
        section_filter = None
    elif state.get("questions"):
        # Follow-up question: use last question's topic
        last_q = state["questions"][-1]
        query = last_q.get("text", "")
        section_filter = last_q.get("category", None)
    else:
        query = f"{state.get('job_role', '')} {state.get('job_description', '')}".strip()
        section_filter = None

    if not resume_id or not query:
        return {"retrieved_chunks": []}

    try:
        chunks = retrieve_chunks(
            resume_id=resume_id,
            query=query,
            top_k=5,
            section_filter=section_filter,
        )
    except Exception as e:
        logger.warning("chunk_retrieval_failed", resume_id=resume_id, error=str(e))
        chunks = []

    logger.info(
        "chunks_retrieved",
        query=query[:50],
        count=len(chunks),
        resume_id=resume_id,
    )

    return {"retrieved_chunks": chunks}
