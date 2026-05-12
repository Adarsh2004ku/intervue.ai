from typing import Any, Dict, List, NotRequired, Optional, TypedDict
"""
InterviewState — shared memory across all LangGraph agents.
This TypedDict defines every field that flows through the interview.
All agents read from and write to this single state object.
"""

class InterviewState(TypedDict):
    # --- Identity ---
    user_id: str                      # Candidate's Supabase user ID
    resume_id: str                    # Which resume to use for retrieval
    job_role: str                     # e.g., "Software Engineer at Google"
    job_description: NotRequired[str] # Optional JD pasted by the candidate
    resume_summary: NotRequired[Dict[str, Any]]

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
