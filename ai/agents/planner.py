import json
from backend.core.config import settings
from backend.db.session import supabase
from ai.agents.llm import invoke_llm_text
from ai.personas.interviewer_personas import get_persona
from ai.agents.state import InterviewState, empty_interview_state_fields
from backend.core.logging import get_logger
from backend.services.interview.topic_profile import fetch_strong_topics, fetch_weak_topics

"""
Planner Agent — the first agent in the LangGraph.
Reads job role, resume, and user's weak topics.
Generates a structured interview plan that biases toward weak areas.
"""
logger = get_logger("planner")


def _persona_flow_text(persona: dict) -> str:
    flow = persona.get("interview_flow", [])
    if not flow:
        return "No explicit persona flow configured."

    lines = []
    for step in flow:
        signals = ", ".join(step.get("signals", [])) or "general signal"
        lines.append(
            f"- {step.get('phase')}: {step.get('category')} | "
            f"goal={step.get('goal')} | signals={signals} | "
            f"default_count={step.get('default_count', 1)}"
        )
    return "\n".join(lines)


def _fallback_interview_plan(
    *,
    persona: dict,
    job_role: str,
    interview_mode: str,
    difficulty: str,
) -> list[dict]:
    flow = persona.get("interview_flow", [])
    if not flow:
        return [
            {
                "phase": "resume_deep_dive",
                "category": "Resume Deep Dive",
                "topic": job_role or "Relevant experience",
                "count": 2,
                "difficulty": difficulty,
                "focus": "project ownership, trade-offs, and validation",
                "question_type": "resume_deep_dive",
                "success_signal": "Candidate explains real work with measurable impact.",
            },
            {
                "phase": "system_design_case",
                "category": "System Design",
                "topic": f"{job_role or 'Role'} architecture case",
                "count": 2,
                "difficulty": difficulty,
                "focus": "requirements, scale, data model, APIs, trade-offs, and rollout",
                "question_type": "case_study",
                "success_signal": "Candidate clarifies constraints and makes sensible trade-offs.",
            },
        ]

    plan = []
    for step in flow:
        phase = step.get("phase", "interview")
        category = step.get("category", "Interview")
        count = step.get("default_count", 1)
        if phase == "opening":
            topic = f"{job_role or 'Role'} background and motivation"
            focus = "concise background, role alignment, and agenda confirmation"
            question_type = "opening"
        elif "system" in phase or "architecture" in phase:
            topic = f"{job_role or 'Role'} architecture case"
            focus = "requirements, scale, APIs, storage, bottlenecks, observability, and rollout"
            question_type = "system_design_case"
        elif "case" in phase or "product" in phase:
            topic = f"{job_role or 'Role'} product case"
            focus = "problem framing, prioritization, metrics, risks, and launch plan"
            question_type = "case_study"
        elif "behavior" in phase or "team" in phase:
            topic = "Behavioral evidence"
            focus = "STAR example, conflict, feedback, ownership, and reflection"
            question_type = "behavioral"
        elif phase == "closing":
            topic = "Candidate questions"
            focus = "candidate curiosity and role understanding"
            question_type = "closing"
        else:
            topic = job_role or category
            focus = step.get("goal") or "role-relevant evidence"
            question_type = "resume_deep_dive"

        plan.append({
            "phase": phase,
            "category": category,
            "topic": topic,
            "count": count,
            "difficulty": difficulty,
            "focus": focus,
            "question_type": question_type,
            "success_signal": (step.get("signals") or [step.get("goal") or "clear signal"])[0],
        })
    return plan


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
    weak_topics = fetch_weak_topics(user_id)
    strong_topics = fetch_strong_topics(user_id)
    difficulty_profile = _get_difficulty_profile(user_id)

    persona = get_persona(interview_mode)

    prompt = f"""You are an interview planner for {persona['name']}.
    Job Role: {job_role}
    Job Description: {job_description[:3000] if job_description else 'Not provided'}
    Interview Mode: {interview_mode} ({persona['style']})
    Persona opening line: {persona.get('opening_line', '')}
    Candidate's Weak Topics: {weak_topics if weak_topics else 'None detected yet'}
    Candidate's Strong Topics: {strong_topics if strong_topics else 'None detected yet'}
    Difficulty Profile: {difficulty_profile}
    Resume Summary: {json.dumps(resume_summary)[:2000]}

    Persona interview flow:
    {_persona_flow_text(persona)}

    Create a realistic interview plan for {settings.max_questions_per_interview} questions.

    Rules:
    1. Follow the persona interview flow in order.
    2. Include at least one resume/project deep dive when resume context exists.
    3. For technical or startup modes, include a realistic system design, architecture, or product case study stage.
    4. Include behavioral evidence and closing/candidate-question stages.
    5. Bias follow-ups toward weak topics when they exist, but do not skip the real interview progression.
    6. Adjust difficulty based on the candidate's profile.

    Return ONLY valid JSON:
    {{
        "difficulty": "medium",
        "interview_plan": [
            {{
                "phase": "resume_deep_dive",
                "category": "Resume Deep Dive",
                "topic": "Most relevant backend project",
                "count": 2,
                "difficulty": "medium",
                "focus": "ownership, trade-offs, validation",
                "question_type": "resume_deep_dive",
                "success_signal": "Candidate explains real decisions and measurable impact"
            }},
            {{
                "phase": "system_design_case",
                "category": "System Design",
                "topic": "Design a job-matching notification system",
                "count": 2,
                "difficulty": "hard",
                "focus": "requirements, APIs, data model, scale, reliability, observability",
                "question_type": "case_study",
                "success_signal": "Candidate clarifies constraints and defends trade-offs"
            }}
        ]
    }}"""

    try:
        content = invoke_llm_text(
            prompt,
            temperature=0.2,
            request_timeout=20,
            purpose="interview_planning",
        ).strip()
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
            "interview_plan": plan_data.get("interview_plan", []) or _fallback_interview_plan(
                persona=persona,
                job_role=job_role,
                interview_mode=interview_mode,
                difficulty=plan_data.get("difficulty", "medium"),
            ),
            "weak_topics": weak_topics,
            "strong_topics": strong_topics,
            "difficulty_profile": difficulty_profile,
            **empty_interview_state_fields(),
        }
    except (json.JSONDecodeError, Exception) as e:
        logger.error("planner_failed", error=str(e))
        difficulty = "medium"
        return {
            "difficulty": difficulty,
            "interview_plan": _fallback_interview_plan(
                persona=persona,
                job_role=job_role,
                interview_mode=interview_mode,
                difficulty=difficulty,
            ),
            "weak_topics": weak_topics,
            "strong_topics": strong_topics,
            "difficulty_profile": difficulty_profile,
            **empty_interview_state_fields(),
        }
