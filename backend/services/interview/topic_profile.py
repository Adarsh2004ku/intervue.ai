from typing import Literal

from backend.core.logging import get_logger
from backend.db.session import supabase


logger = get_logger("topic_profile")


def fetch_topics_by_score(
    user_id: str,
    *,
    threshold: int,
    comparison: Literal["lt", "gte"],
) -> list[str]:
    try:
        query = (
            supabase.table("user_topic_profiles")
            .select("topic, avg_score")
            .eq("user_id", user_id)
        )
        if comparison == "lt":
            result = query.lt("avg_score", threshold).order("avg_score").execute()
        else:
            result = query.gte("avg_score", threshold).execute()
        return [row["topic"] for row in (result.data or [])]
    except Exception as exc:
        logger.warning(
            "topic_profile_fetch_failed",
            comparison=comparison,
            threshold=threshold,
            error=str(exc),
        )
        return []


def fetch_weak_topics(user_id: str, threshold: int = 60) -> list[str]:
    return fetch_topics_by_score(user_id, threshold=threshold, comparison="lt")


def fetch_strong_topics(user_id: str, threshold: int = 75) -> list[str]:
    return fetch_topics_by_score(user_id, threshold=threshold, comparison="gte")
