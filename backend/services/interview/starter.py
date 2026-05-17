from typing import Any


INTRO_QUESTION_TEXT = (
    "To start, please give me a brief introduction about yourself, "
    "your background, and the experience or project most relevant to this role."
)
INTRO_QUESTION_REASON = (
    "Every interview starts with a brief candidate introduction before role-specific questions."
)


def build_starter_interview_plan(
    *,
    job_role: str,
    interview_mode: str,
) -> list[dict[str, Any]]:
    """Fast local plan used so /start does not wait on planner LLM latency."""
    role = job_role or "this role"
    is_hr = interview_mode == "hr"
    is_startup = interview_mode == "startup"

    plan = [
        {
            "phase": "opening",
            "category": "Introduction",
            "topic": "Candidate background",
            "count": 1,
            "difficulty": "warmup",
            "focus": "brief candidate introduction and role alignment",
            "question_type": "opening",
            "success_signal": "Candidate gives a concise background and relevant experience.",
        },
        {
            "phase": "resume_deep_dive",
            "category": "Resume Deep Dive",
            "topic": f"{role} relevant experience",
            "count": 2,
            "difficulty": "medium",
            "focus": "ownership, trade-offs, measurable impact, and validation",
            "question_type": "resume_deep_dive",
            "success_signal": "Candidate explains real work with clear ownership and outcomes.",
        },
    ]

    if is_hr:
        plan.append({
            "phase": "behavioral",
            "category": "Behavioral",
            "topic": "Collaboration and growth",
            "count": 3,
            "difficulty": "medium",
            "focus": "conflict, feedback, ownership, and reflection",
            "question_type": "behavioral",
            "success_signal": "Candidate uses concrete examples and reflection.",
        })
    elif is_startup:
        plan.append({
            "phase": "product_case",
            "category": "Product Case",
            "topic": f"{role} product delivery case",
            "count": 3,
            "difficulty": "medium",
            "focus": "prioritization, constraints, metrics, and launch trade-offs",
            "question_type": "case_study",
            "success_signal": "Candidate makes pragmatic trade-offs and defines success metrics.",
        })
    else:
        plan.append({
            "phase": "system_design_case",
            "category": "System Design",
            "topic": f"{role} architecture case",
            "count": 3,
            "difficulty": "medium",
            "focus": "requirements, APIs, data model, scale, reliability, and validation",
            "question_type": "case_study",
            "success_signal": "Candidate clarifies constraints and defends trade-offs.",
        })

    plan.append({
        "phase": "closing",
        "category": "Candidate Questions",
        "topic": f"{role} role fit",
        "count": 1,
        "difficulty": "warmup",
        "focus": "candidate questions and role understanding",
        "question_type": "closing",
        "success_signal": "Candidate asks thoughtful questions about the role or team.",
    })

    return plan


def first_intro_question_payload(
    *,
    interview_mode: str,
    job_role: str,
    job_description: str,
    interview_id: str,
) -> dict[str, Any]:
    return {
        "text": INTRO_QUESTION_TEXT,
        "category": "Introduction",
        "topic": "Candidate background",
        "difficulty": "warmup",
        "why_asked": INTRO_QUESTION_REASON,
        "is_weakness_focused": False,
        "order_idx": 0,
    }
