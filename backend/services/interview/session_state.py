from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from backend.core.config import settings
from backend.core.logging import get_logger
from backend.services.cache.redis_client import get_redis_client


logger = get_logger("interview_session_state")


def _empty_interview_session() -> dict:
    return {
        "frames": [],
        "audio": [],
        "job_description": "",
        "job_role": "",
        "interview_mode": "",
        "agent_state": {},
    }


_memory_sessions = defaultdict(_empty_interview_session)


def _session_key(interview_id: str) -> str:
    return f"interview:session:{interview_id}"


def _normalise_session(session: dict[str, Any] | None) -> dict[str, Any]:
    base = _empty_interview_session()
    if not isinstance(session, dict):
        return base

    for key, default in base.items():
        value = session.get(key, default)
        if key in {"frames", "audio"} and not isinstance(value, list):
            value = []
        if key == "agent_state" and not isinstance(value, dict):
            value = {}
        base[key] = value
    return base


def get_interview_session(interview_id: str) -> dict[str, Any]:
    client = get_redis_client()
    if client is not None:
        try:
            payload = client.get(_session_key(interview_id))
            if payload:
                return _normalise_session(json.loads(payload))
        except Exception as exc:
            logger.warning(
                "redis_session_read_failed",
                interview_id=interview_id,
                error=str(exc),
            )

    return _normalise_session(_memory_sessions[interview_id])


def save_interview_session(interview_id: str, session: dict[str, Any]) -> None:
    normalised = _normalise_session(session)
    _memory_sessions[interview_id] = normalised

    client = get_redis_client()
    if client is None:
        return

    try:
        client.setex(
            _session_key(interview_id),
            settings.redis_session_ttl_seconds,
            json.dumps(normalised, default=str),
        )
    except Exception as exc:
        logger.warning(
            "redis_session_write_failed",
            interview_id=interview_id,
            error=str(exc),
        )


def append_session_item(interview_id: str, field: str, item: dict[str, Any]) -> None:
    session = get_interview_session(interview_id)
    values = session.setdefault(field, [])
    if not isinstance(values, list):
        values = []
        session[field] = values
    values.append(item)
    save_interview_session(interview_id, session)


def get_session_frames(interview_id: str) -> list[dict[str, Any]]:
    frames = get_interview_session(interview_id).get("frames") or []
    return frames if isinstance(frames, list) else []


def reset_interview_session(
    interview_id: str,
    *,
    job_description: str = "",
    job_role: str = "",
    interview_mode: str = "",
    agent_state: dict | None = None,
) -> None:
    save_interview_session(interview_id, {
        "frames": [],
        "audio": [],
        "job_description": job_description,
        "job_role": job_role,
        "interview_mode": interview_mode,
        "agent_state": agent_state or {},
    })


def with_session_interview_context(
    interview_id: str,
    interview: dict,
) -> dict:
    session = get_interview_session(interview_id)
    enriched = dict(interview)
    for field in ("job_description", "job_role", "interview_mode"):
        if not enriched.get(field) and session.get(field):
            enriched[field] = session[field]
    return enriched


def get_agent_state(interview_id: str) -> dict:
    return dict(get_interview_session(interview_id).get("agent_state") or {})


def set_agent_state(interview_id: str, agent_state: dict) -> None:
    session = get_interview_session(interview_id)
    session["agent_state"] = agent_state
    save_interview_session(interview_id, session)
