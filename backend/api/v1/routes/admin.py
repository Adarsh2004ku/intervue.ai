"""
Admin routes:
- GET /dashboard — KPIs overview
- GET /costs — LLM cost analytics
- GET /metrics — System metrics
"""

from datetime import date
from fastapi import APIRouter
from backend.db.session import supabase, redis_client
from backend.core.logging import get_logger

logger = get_logger("admin_routes")
router = APIRouter()


@router.get("/dashboard")
async def admin_dashboard():
    """Get admin dashboard KPIs."""
    # Total interviews
    interviews = supabase.table("interviews").select("id, status, overall_score").execute()
    total_interviews = len(interviews.data) if interviews.data else 0
    completed = [i for i in (interviews.data or []) if i.get("status") == "completed"]
    avg_score = (
        sum(i.get("overall_score", 0) for i in completed) / len(completed)
        if completed else 0
    )

    # Total users
    users = supabase.table("users").select("id").execute()
    total_users = len(users.data) if users.data else 0

    # Today's costs
    today = str(date.today())
    costs = supabase.table("ai_costs").select("cost_inr").gte("created_at", today).execute()
    today_cost = sum(c.get("cost_inr", 0) for c in (costs.data or []))

    return {
        "total_interviews": total_interviews,
        "completed_interviews": len(completed),
        "average_score": round(avg_score, 1),
        "total_users": total_users,
        "today_cost_inr": round(today_cost, 2),
    }


@router.get("/costs")
async def get_costs(days: int = 7):
    """Get LLM cost breakdown for the last N days."""
    from datetime import timedelta
    start_date = str(date.today() - timedelta(days=days))

    result = (
        supabase.table("ai_costs")
        .select("interview_id, model, call_type, cost_inr, tokens_in, tokens_out, latency_ms, created_at")
        .gte("created_at", start_date)
        .order("created_at", desc=True)
        .execute()
    )

    records = result.data or []
    return {
        "days": days,
        "total_cost_inr": round(sum(item.get("cost_inr", 0) for item in records), 4),
        "total_tokens": sum(
            (item.get("tokens_in", 0) or 0) + (item.get("tokens_out", 0) or 0)
            for item in records
        ),
        "records": records,
    }


@router.get("/metrics")
async def get_metrics():
    """Get system-level metrics for monitoring."""
    metrics = {"status": "ok"}

    try:
        metrics["redis_connected"] = redis_client.ping()
        metrics["redis_memory"] = redis_client.info().get("used_memory_human", "unknown")
    except Exception as e:
        metrics["redis_connected"] = False
        metrics["redis_error"] = str(e)[:100]

    return metrics
