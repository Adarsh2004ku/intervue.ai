import random
import json
from langchain_google_genai import ChatGoogleGenerativeAI
from backend.core.config import settings
from ai.personas.interviewer_personas import get_persona
from ai.agents.state import InterviewState
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

    llm = ChatGoogleGenerativeAI(model=settings.primary_llm, temperature=0.4)

    prompt = f"""You are {persona['name']}, conducting an interview.

    Persona Style: {persona['style']}
    Tone: {persona['tone']}
    Question Style Rules: {chr(10).join('- ' + s for s in persona['question_style'])}

    Topic to test: {topic_info.get('topic', '')}
    Category: {topic_info.get('category', '')}
    Difficulty: {topic_info.get('difficulty', 'medium')}
    Focus: {topic_info.get('focus', '')}
    Question Type: {question_type}

    Resume Context:
    {context_text}

    Previous Q&A History:
    {history}

    Weak topics for this candidate: {state.get('weak_topics', [])}

    Generate ONE interview question. Stay strictly in character.
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
        content = response.content.strip()
        if content.startswith("```"):
            parts = content.split("```")
            if len(parts) >= 2:
                content = parts[1]
            if content.startswith("json"):
                content = content[4:]

        question_data = json.loads(content.strip())
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
        fallback = {
            "text": f"Tell me about your experience with {topic_info.get('topic', 'your field')}.",
            "category": topic_info.get("category", "General"),
            "topic": topic_info.get("topic", ""),
            "difficulty": topic_info.get("difficulty", "medium"),
            "why_asked": "Fallback question due to generation error",
            "is_weakness_focused": False,
            "order_idx": len(questions),
        }
        return {"questions": questions + [fallback]}