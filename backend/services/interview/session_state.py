from collections import defaultdict


def _empty_interview_session() -> dict:
    return {
        "frames": [],
        "audio": [],
        "job_description": "",
        "job_role": "",
        "interview_mode": "",
        "agent_state": {},
    }


interview_sessions = defaultdict(_empty_interview_session)


def reset_interview_session(
    interview_id: str,
    *,
    job_description: str = "",
    job_role: str = "",
    interview_mode: str = "",
    agent_state: dict | None = None,
) -> None:
    interview_sessions[interview_id] = {
        "frames": [],
        "audio": [],
        "job_description": job_description,
        "job_role": job_role,
        "interview_mode": interview_mode,
        "agent_state": agent_state or {},
    }


def with_session_interview_context(
    interview_id: str,
    interview: dict,
) -> dict:
    session = interview_sessions[interview_id]
    enriched = dict(interview)
    for field in ("job_description", "job_role", "interview_mode"):
        if not enriched.get(field) and session.get(field):
            enriched[field] = session[field]
    return enriched


def get_agent_state(interview_id: str) -> dict:
    return dict(interview_sessions[interview_id].get("agent_state") or {})


def set_agent_state(interview_id: str, agent_state: dict) -> None:
    interview_sessions[interview_id]["agent_state"] = agent_state
