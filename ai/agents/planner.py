import json
from backend.core.config import settings
from backend.db.session import supabase
from ai.personas.interviewer_personas import get_persona
from ai.agents.state import InterviewState
from backend.services.llm.provider import get_gemini_direct, parse_llm_json
from backend.core.logging import get_logger

"""
Planner Agent — the first agent in the LangGraph.
Reads job role, resume, and user's weak topics.
Generates a structured interview plan that biases toward weak areas.
"""
logger = get_logger("planner")

def _fetch_weak_topics(user_id:str, threshold:int = 60)->list[str]:
    """Fetch topics where user's avg_score is below threshold."""
    try :
        result = (
            supabase.table("user_topic_profiles")
            .select("topic, avg_score")
            .eq("user_id", user_id)
            .lt("avg_score", threshold)
            .order("avg_score")
            .execute()
        )
        return [r["topic"] for r in (result.data or [])]
    except Exception as e:
        logger.warning("weak_topics_fetch_failed", error=str(e))
        return [] 

def _fetch_strong_topics(user_id: str, threshold: int = 75) -> list[str]:
    """Fetch topics where user's avg_score is above threshold."""
    try:
        result = (
            supabase.table("user_topic_profiles")
            .select("topic, avg_score")
            .eq("user_id", user_id)
            .gte("avg_score", threshold)
            .execute()
        )
        return [r["topic"] for r in (result.data or [])]
    except Exception as e:
        logger.warning("strong_topics_fetch_failed", error=str(e))
        return []
    

def _get_difficulty_profile(user_id: str) -> str:
    """Get user's persisted difficulty profile from DB."""
    try:
        result = (
            supabase.table("users")
            .select("difficulty_profile")
            .eq("id", user_id)
            .single()
            .execute()
        )
        return result.data.get("difficulty_profile", "beginner") if result.data else "beginner"
    except Exception:
        return "beginner"

def planner_agent(state: InterviewState) -> dict:
    """
    Plan the interview based on job role, resume, and weakness profile.
    Returns updated state fields: difficulty, interview_plan, weak_topics, etc.
    """
    user_id = state.get("user_id", "")
    job_role = state.get("job_role", "")
    job_description = state.get("job_description", "")
    interview_mode = state.get("interview_mode", "faang")
    resume_summary = state.get("resume_summary", {})

    # Fetch user's historical topic performance
    weak_topics = _fetch_weak_topics(user_id)
    strong_topics = _fetch_strong_topics(user_id)
    difficulty_profile = _get_difficulty_profile(user_id)

    persona = get_persona(interview_mode)

    llm = get_gemini_direct(temperature=0.2)


    prompt = f"""You are an interview planner for {persona['name']}.
    Job Role: {job_role}
    Job Description:
    {job_description[:3000] if job_description else "No detailed job description provided."}
    Interview Mode: {interview_mode} ({persona['style']})
    Candidate's Weak Topics: {weak_topics if weak_topics else 'None detected yet'}
    Candidate's Strong Topics: {strong_topics if strong_topics else 'None detected yet'}
    Difficulty Profile: {difficulty_profile}
    Resume Summary: {json.dumps(resume_summary)[:2000]}

    Create an interview plan for {settings.max_questions_per_interview} questions.

    Rules:
    1. The first question must be a brief introduction prompt.
    2. The second and third questions should come from the candidate's projects or shipped work.
    3. Later questions should connect resume evidence to the job role and job description.
    4. Allocate weak-topic questions after the project/resume grounding questions.
    5. Adjust difficulty based on the candidate's profile.

    Return ONLY valid JSON:
    {{
        "difficulty": "medium",
        "interview_plan": [
            {{"category": "DSA", "topic": "Binary Trees", "count": 2, "difficulty": "medium", "focus": "traversal algorithms"}},
            {{"category": "System Design", "topic": "Caching", "count": 2, "difficulty": "hard", "focus": "distributed caching"}}
        ]
    }}"""

    try:
        response = llm.invoke(prompt)
        plan_data = parse_llm_json(response.content)

        logger.info(
            "interview_planned",
            difficulty=plan_data.get("difficulty"),
            categories=len(plan_data.get("interview_plan", [])),
            weak_topics=weak_topics,
        )
        return {
            "difficulty": plan_data.get("difficulty", "medium"),
            "interview_plan": plan_data.get("interview_plan", []),
            "weak_topics": weak_topics,
            "strong_topics": strong_topics,
            "difficulty_profile": difficulty_profile,
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
    except (json.JSONDecodeError, Exception) as e:
        logger.error("planner_failed", error=str(e))
        # Fallback plan
        return {
            "difficulty": "medium",
            "interview_plan": [
                {"category": "Intro", "topic": "Candidate introduction", "count": 1, "difficulty": "easy", "focus": "brief background and target role"},
                {"category": "Projects", "topic": "Resume projects", "count": 2, "difficulty": "medium", "focus": "project ownership, architecture, impact, and trade-offs"},
                {"category": "Role Fit", "topic": job_role, "count": 3, "difficulty": "medium", "focus": "job description alignment"},
                {"category": "Technical", "topic": job_role, "count": 4, "difficulty": "medium", "focus": "core skills and problem solving"},
            ],
            "weak_topics": weak_topics,
            "strong_topics": strong_topics,
            "difficulty_profile": difficulty_profile,
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
