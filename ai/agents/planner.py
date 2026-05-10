import json
from langchain_google_genai import ChatGoogleGenerativeAI
from backend.core.config import settings
from backend.db.session import supabase
from ai.personas.interviewer_personas import get_persona
from ai.agents.state import InterviewState
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
    interview_mode = state.get("interview_mode", "faang")
    resume_summary = state.get("resume_summary", {})

    # Fetch user's historical topic performance
    weak_topics = _fetch_weak_topics(user_id)
    strong_topics = _fetch_strong_topics(user_id)
    difficulty_profile = _get_difficulty_profile(user_id)

    persona = get_persona(interview_mode)

    llm = ChatGoogleGenerativeAI(model=settings.primary_llm, temperature=0.2)


    prompt = f"""You are an interview planner for {persona['name']}.
    Job Role: {job_role}
    Interview Mode: {interview_mode} ({persona['style']})
    Candidate's Weak Topics: {weak_topics if weak_topics else 'None detected yet'}
    Candidate's Strong Topics: {strong_topics if strong_topics else 'None detected yet'}
    Difficulty Profile: {difficulty_profile}
    Resume Summary: {json.dumps(resume_summary)[:2000]}

    Create an interview plan for {settings.max_questions_per_interview} questions.

    Rules:
    1. Allocate 60% of questions to weak topics (if any exist)
    2. Allocate 30% to new/untested topics from the job role
    3. Allocate 10% to strong topics (confirmation)
    4. Adjust difficulty based on the candidate's profile

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
        content = response.content.strip()
        if content.startswith("```"):
            parts = content.split("```")
            if len(parts) >= 2:
                content = parts[1]
            if content.startswith("json"):
                content = content[4:]

        plan_data = json.loads(content.strip())

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
                {"category": "Technical", "topic": job_role, "count": 5, "difficulty": "medium", "focus": "general"},
                {"category": "HR", "topic": "Behavioural", "count": 3, "difficulty": "easy", "focus": "STAR method"},
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