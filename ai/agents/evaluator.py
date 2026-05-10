import json
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI
from backend.core.config import settings
from ai.agents.state import InterviewState
from backend.core.logging import get_logger

"""
Evaluator Agent — scores candidate answers.
Produces a structured evaluation with sub-scores for accuracy,
clarity, and depth, plus chain-of-thought reasoning.
Uses Pydantic structured output for format enforcement.
"""

logger = get_logger("evaluator_agent")


class EvaluationResult(BaseModel):
    """Structured output schema for answer evaluation."""
    score: int = Field(ge=0, le=100, description="Overall weighted score 0-100")
    accuracy_score: int = Field(ge=0, le=100, description="Factual correctness")
    clarity_score: int = Field(ge=0, le=100, description="Communication clarity")
    depth_score: int = Field(ge=0, le=100, description="Depth of understanding")
    cot_reasoning: str = Field(description="Chain-of-thought explanation for scores")


def evaluator_agent(state: InterviewState) -> dict:
    """
    Evaluate the candidate's last answer.
    Returns updated state with evaluation appended.
    """
    questions = state.get("questions", [])
    answers = state.get("answers", [])

    if not questions or not answers:
        return {"evaluations": state.get("evaluations", [])}

    current_question = questions[-1]
    current_answer = answers[-1]

    llm = ChatGoogleGenerativeAI(model=settings.primary_llm, temperature=0.1)

    prompt = f"""You are an expert interview evaluator. Evaluate this answer carefully.

    Question: {current_question.get('text', '')}
    Question Category: {current_question.get('category', '')}
    Question Difficulty: {current_question.get('difficulty', 'medium')}
    Candidate's Answer: {current_answer.get('transcript', '')}

    Evaluate on three dimensions:
    1. Accuracy (0-100): Is the answer factually correct and relevant?
    2. Clarity (0-100): Is the answer well-structured and clearly communicated?
    3. Depth (0-100): Does it demonstrate deep understanding beyond surface level?

    Overall Score = 0.4 × accuracy + 0.3 × clarity + 0.3 × depth

    Provide chain-of-thought reasoning explaining your scoring.

    Return ONLY valid JSON:
    {{
        "score": 75,
        "accuracy_score": 80,
        "clarity_score": 70,
        "depth_score": 65,
        "cot_reasoning": "The candidate correctly identified the key concept but missed edge cases..."
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

        eval_data = json.loads(content.strip())

        # Clamp scores to 0-100
        for key in ["score", "accuracy_score", "clarity_score", "depth_score"]:
            eval_data[key] = max(0, min(100, eval_data.get(key, 0)))

        logger.info(
            "answer_evaluated",
            score=eval_data.get("score"),
            question_topic=current_question.get("topic"),
        )

        evaluations = state.get("evaluations", []) + [eval_data]

        # Update session topic scores
        session_scores = state.get("session_topic_scores", {})
        topic = current_question.get("topic", "general")
        session_scores[topic] = eval_data.get("score", 0)

        return {
            "evaluations": evaluations,
            "session_topic_scores": session_scores,
        }

    except (json.JSONDecodeError, Exception) as e:
        logger.error("evaluation_failed", error=str(e))
        fallback_eval = {
            "score": 50,
            "accuracy_score": 50,
            "clarity_score": 50,
            "depth_score": 50,
            "cot_reasoning": f"Evaluation parsing failed: {str(e)[:100]}",
        }
        return {"evaluations": state.get("evaluations", []) + [fallback_eval]}