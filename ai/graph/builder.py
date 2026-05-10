

from langgraph.graph import StateGraph, END
from ai.agents.state import InterviewState
from ai.agents.planner import planner_agent
from ai.agents.retriever import retriever_agent
from ai.agents.generator import generator_agent
from ai.agents.evaluator import evaluator_agent
from ai.agents.coach import coach_agent
from backend.core.config import settings
from backend.core.logging import get_logger

logger = get_logger("graph_builder")
"""
LangGraph StateGraph builder.
Defines the interview flow:
  START → Planner → Retriever → Generator → [answer] → Evaluator
    → (questions remaining?) → Retriever (loop) or Coach → END
"""

def questions_remaining(state: InterviewState) -> str:
    """
    Conditional edge: check if there are more questions to ask.
    Returns 'continue' to loop back, or 'end' to proceed to Coach.
    """
    current_index = state.get("current_index", 0)
    max_questions = settings.max_questions_per_interview
    questions = state.get("questions", [])

    if current_index >= max_questions:
        return "end"

    # Also end if we've evaluated all generated questions
    evaluations = state.get("evaluations", [])
    if len(evaluations) >= max_questions:
        return "end"

    return "continue"


def build_interview_graph() -> StateGraph:
    """
    Build and compile the LangGraph interview state machine.
    """
    graph = StateGraph(InterviewState)

    # Add agent nodes
    graph.add_node("planner", planner_agent)
    graph.add_node("retriever", retriever_agent)
    graph.add_node("generator", generator_agent)
    graph.add_node("evaluator", evaluator_agent)
    graph.add_node("coach", coach_agent)

    # Set entry point
    graph.set_entry_point("planner")

    # Define edges
    graph.add_edge("planner", "retriever")
    graph.add_edge("retriever", "generator")
    # generator → (wait for answer) → evaluator (handled by WebSocket)
    graph.add_edge("generator", "evaluator")
    graph.add_conditional_edges(
        "evaluator",
        questions_remaining,
        {"continue": "retriever", "end": "coach"},
    )
    graph.add_edge("coach", END)

    compiled = graph.compile()
    logger.info("interview_graph_built")
    return compiled