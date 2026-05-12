import random
import json
from backend.core.config import settings
from ai.personas.interviewer_personas import get_persona
from ai.agents.state import InterviewState
from backend.services.llm.provider import get_gemini_direct, parse_llm_json
from backend.core.logging import get_logger

logger = get_logger("generator_agent")

"""
Question Generator Agent — generates the next interview question.
Uses retrieved resume chunks, Q&A history, persona, and weak topics
to create personalized, adaptive questions.
If the last score was below threshold, generates a follow-up instead.
"""

def _get_next_topic(state: InterviewState) -> dict:
    """Determine the next topic to ask about, with weakness bias."""
    current_index = state.get("current_index", 0)
    interview_plan = state.get("interview_plan", [])
    weak_topics = state.get("weak_topics", [])

    if current_index < len(interview_plan):
        return interview_plan[current_index]

    # Past the plan — pick from weak topics with 70% probability
    if weak_topics and random.random() < 0.7:
        return {
            "category": "Weakness Focus",
            "topic": random.choice(weak_topics),
            "difficulty": state.get("difficulty", "medium"),
            "focus": "addressing weakness",
        }

    return {"category": "General", "topic": state.get("job_role", ""), "difficulty": "medium", "focus": "general"}


def fallback_question_for_index(
    state: InterviewState,
    questions: list[dict],
    reason: str = "Fallback question due to generation error",
) -> dict:
    """Build a deterministic non-repeating fallback question."""
    job_role = state.get("job_role", "this role") or "this role"
    order_idx = len(questions)
    templates = [
        {
            "text": (
                "Give me a brief introduction, focusing on your background, strongest project, "
                "and why this role is a fit."
            ),
            "category": "Intro",
            "topic": "Candidate introduction",
            "difficulty": "easy",
        },
        {
            "text": (
                "Walk me through a project from your resume that best demonstrates your fit for "
                f"{job_role}. What did you own, and what trade-offs did you make?"
            ),
            "category": "Projects",
            "topic": "Resume projects",
            "difficulty": "medium",
        },
        {
            "text": (
                "Pick a technical decision from one of your projects. What alternatives did you consider, "
                "and how did you validate the choice?"
            ),
            "category": "Projects",
            "topic": "Technical decisions",
            "difficulty": "medium",
        },
        {
            "text": (
                "Tell me about a difficult bug, production issue, or edge case you handled. "
                "How did you isolate the root cause?"
            ),
            "category": "Technical",
            "topic": "Debugging",
            "difficulty": "medium",
        },
        {
            "text": (
                f"Imagine a system relevant to {job_role} has to support significantly more users. "
                "What would you measure first, and what would you change?"
            ),
            "category": "Technical",
            "topic": "Scalability",
            "difficulty": "medium",
        },
        {
            "text": (
                "Describe a time you worked with teammates or stakeholders under ambiguity. "
                "How did you keep the work moving?"
            ),
            "category": "Behavioral",
            "topic": "Collaboration",
            "difficulty": "medium",
        },
    ]

    question = templates[order_idx % len(templates)].copy()
    if order_idx >= len(templates):
        question["text"] = f"{question['text']} Use a different example than the ones you already discussed."

    question.update({
        "why_asked": reason,
        "is_weakness_focused": False,
        "order_idx": order_idx,
    })
    return question


def generator_agent(state: InterviewState) -> dict:
    """
    Generate the next interview question.
    If last score < threshold, generates a follow-up.
    Returns updated state with new question appended.
    """
    persona = get_persona(state.get("interview_mode", "faang"))
    topic_info = _get_next_topic(state)
    retrieved_chunks = state.get("retrieved_chunks", [])
    questions = state.get("questions", [])
    evaluations = state.get("evaluations", [])
    current_index = state.get("current_index", 0)
    resume_summary = state.get("resume_summary", {})
    job_description = state.get("job_description", "")
    projects = resume_summary.get("projects", []) if isinstance(resume_summary, dict) else []
    skills = resume_summary.get("skills", []) if isinstance(resume_summary, dict) else []

    # Build context from retrieved chunks
    context_text = "\n".join(
        [c.get("chunk_text", "") for c in retrieved_chunks[:3]]
    )[:2000]

    # Build Q&A history summary (last 3 exchanges)
    history = ""
    for i in range(max(0, len(questions) - 3), len(questions)):
        q = questions[i]
        a = state["answers"][i] if i < len(state.get("answers", [])) else {}
        e = evaluations[i] if i < len(evaluations) else {}
        history += f"Q: {q.get('text', '')}\nA: {a.get('transcript', 'N/A')}\nScore: {e.get('score', 'N/A')}\n\n"

    # Determine question type
    last_score = evaluations[-1].get("score") if evaluations else None
    if last_score is not None and last_score < settings.weak_score_threshold:
        question_type = "follow_up"
    else:
        question_type = "new"

    llm = get_gemini_direct(temperature=0.4)

    prompt = f"""You are {persona['name']}, conducting an interview.

    Persona Style: {persona['style']}
    Tone: {persona['tone']}
    Question Style Rules: {chr(10).join('- ' + s for s in persona['question_style'])}

    Interview Progress: question index {current_index}, generated questions so far {len(questions)}
    Topic to test: {topic_info.get('topic', '')}
    Category: {topic_info.get('category', '')}
    Difficulty: {topic_info.get('difficulty', 'medium')}
    Focus: {topic_info.get('focus', '')}
    Question Type: {question_type}

    Candidate Resume Projects:
    {json.dumps(projects[:5])[:2000] if projects else "No explicit projects parsed."}

    Candidate Skills:
    {json.dumps(skills[:20])[:1000] if skills else "No explicit skills parsed."}

    Job Description:
    {job_description[:2500] if job_description else "No detailed job description provided."}

    Resume Context:
    {context_text}

    Previous Q&A History:
    {history}

    Weak topics for this candidate: {state.get('weak_topics', [])}

    Generate ONE interview question. Stay strictly in character.
    If this is question index 0, ask for a brief introduction tied to the target role.
    If this is question index 1 or 2, ask about a specific resume project or shipped work, including ownership, trade-offs, impact, and technical decisions.
    For later questions, connect resume evidence to the job description and adapt based on prior answers.
    {"This is a FOLLOW-UP — dig deeper into the previous topic since the candidate scored low." if question_type == "follow_up" else ""}

    Return ONLY valid JSON:
    {{
        "text": "Your question here",
        "category": "{topic_info.get('category', '')}",
        "topic": "{topic_info.get('topic', '')}",
        "difficulty": "{topic_info.get('difficulty', 'medium')}",
        "why_asked": "One sentence explaining why this question was asked",
        "is_weakness_focused": false
    }}"""

    try:
        response = llm.invoke(prompt)
        question_data = parse_llm_json(response.content)
        question_data["order_idx"] = len(questions)

        # Mark if this is a weakness-focused question
        if topic_info.get("topic") in state.get("weak_topics", []):
            question_data["is_weakness_focused"] = True

        logger.info(
            "question_generated",
            topic=question_data.get("topic"),
            difficulty=question_data.get("difficulty"),
            weakness_focused=question_data.get("is_weakness_focused"),
        )

        return {"questions": questions + [question_data]}

    except (json.JSONDecodeError, Exception) as e:
        logger.error("question_generation_failed", error=str(e))
        fallback = fallback_question_for_index(state, questions)
        return {"questions": questions + [fallback]}
