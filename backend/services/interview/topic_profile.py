from backend.core.logging import get_logger
from backend.db.session import supabase


logger = get_logger("topic_profile")


def fetch_topic_profile(
    user_id: str,
    *,
    weak_threshold: int = 60,
    strong_threshold: int = 75,
) -> dict[str, list[str]]:
    try:
        result = (
            supabase.table("user_topic_profiles")
            .select("topic, avg_score")
            .eq("user_id", user_id)
            .execute()
        )
    except Exception as exc:
        logger.warning(
            "topic_profile_fetch_failed",
            weak_threshold=weak_threshold,
            strong_threshold=strong_threshold,
            error=str(exc),
        )
        return {"weak_topics": [], "strong_topics": []}

    weak_topics = []
    strong_topics = []
    for row in result.data or []:
        topic = row.get("topic")
        if not topic:
            continue
        try:
            score = float(row.get("avg_score") or 0)
        except (TypeError, ValueError):
            continue
        if score < weak_threshold:
            weak_topics.append((score, topic))
        if score >= strong_threshold:
            strong_topics.append((score, topic))

    return {
        "weak_topics": [topic for _, topic in sorted(weak_topics)],
        "strong_topics": [topic for _, topic in sorted(strong_topics, reverse=True)],
    }
