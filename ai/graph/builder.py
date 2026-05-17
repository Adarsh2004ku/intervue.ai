from ai.agents.state import InterviewState
from ai.agents.planner import planner_agent
from ai.agents.retriever import retriever_agent
from ai.agents.generator import generator_agent

"""
Utilities for the live interview graph slice.
"""


def run_question_turn(state: InterviewState, *, include_planner: bool = False) -> InterviewState:
    """
    Run the live-interview agent slice used by the backend API.
    The full LangGraph includes evaluator/coach nodes that need an answer first,
    so question turns intentionally run planner/retriever/generator only.
    """
    next_state = dict(state)

    if include_planner or not next_state.get("interview_plan"):
        runtime_fields = {
            key: next_state.get(key)
            for key in (
                "questions",
                "answers",
                "evaluations",
                "speech_metrics",
                "behavior_data",
                "current_index",
                "session_topic_scores",
                "retrieved_chunks",
                "report",
            )
        }
        next_state.update(planner_agent(next_state))
        for key, value in runtime_fields.items():
            if value:
                next_state[key] = value

    next_state.update(retriever_agent(next_state))
    next_state.update(generator_agent(next_state))
    return next_state
