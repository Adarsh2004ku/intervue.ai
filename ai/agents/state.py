from typing import Any, Dict, List, Optional, TypedDict

"""
InterviewState — shared memory across all LangGraph agents.
This TypedDict defines every field that flows through the interview.
All agents read from and write to this single state object.
"""

class InterviewState(TypedDict):
    # --- Identity ---
    user_id: str                      # Candidate's Supabase user ID
    interview_id: str                 # Current interview session ID
    resume_id: str                    # Which resume to use for retrieval
    job_role: str                     # e.g., "Software Engineer at Google"
    job_description: str              # Pasted role description and requirements
    resume_summary: Dict[str, Any]    # Parsed resume JSON used for planner/generator context

    # --- Planner output ---
    difficulty: str                   # 'easy', 'medium', or 'hard'
    interview_plan: List[Dict]        # [{'category': 'DSA', 'count': 3, 'focus': 'trees'}, ...]

    # --- Running interview data ---
    questions: List[Dict]             # All questions generated so far
    answers: List[Dict]               # All transcribed answers
    evaluations: List[Dict]           # All scores and CoT reasoning
    speech_metrics: List[Dict]        # Pace, fillers, pauses per answer
    behavior_data: List[Dict]         # Camera frame analysis results
    current_index: int                # Which question we are on (0-based)

    # --- Weakness & personalization ---
    weak_topics: List[str]            # Loaded from DB at session start
    strong_topics: List[str]          # Topics where avg_score > 75
    session_topic_scores: Dict        # {topic: score} built during session
    interview_mode: str               # 'faang' | 'startup' | 'hr'
    difficulty_profile: str           # 'beginner' | 'intermediate' | 'advanced'

    # --- Retrieval context ---
    retrieved_chunks: List[Dict]      # Current pgvector chunks for context


    # --- Final output ---
    report: Optional[Dict]            # Set by Coach at the end, None until then


def empty_interview_state_fields() -> dict[str, Any]:
    """Return the mutable runtime collections shared by planner and starter flows."""
    return {
        "questions": [],
        "answers": [],
        "evaluations": [],
        "speech_metrics": [],
        "behavior_data": [],
        "current_index": 0,
        "session_topic_scores": {},
        "retrieved_chunks": [],
        "report": None,
    }


def build_interview_state(
    *,
    user_id: str,
    interview_id: str,
    resume_id: str,
    job_role: str,
    job_description: str,
    resume_summary: dict[str, Any],
    interview_mode: str,
    difficulty: str,
    interview_plan: list[dict],
    weak_topics: list[str] | None = None,
    strong_topics: list[str] | None = None,
    difficulty_profile: str = "beginner",
    questions: list[dict] | None = None,
) -> InterviewState:
    state = {
        "user_id": user_id,
        "interview_id": interview_id,
        "resume_id": resume_id,
        "job_role": job_role,
        "job_description": job_description,
        "resume_summary": resume_summary,
        "difficulty": difficulty,
        "interview_plan": interview_plan,
        "weak_topics": weak_topics or [],
        "strong_topics": strong_topics or [],
        "interview_mode": interview_mode,
        "difficulty_profile": difficulty_profile,
        **empty_interview_state_fields(),
    }
    if questions is not None:
        state["questions"] = questions
    return state
