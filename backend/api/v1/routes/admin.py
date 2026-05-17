"""
Admin routes:
- GET /me — verify admin access
- GET /dashboard — KPI overview
- GET /costs — LLM cost analytics
- GET /metrics — system metrics
- GET /overview — consolidated admin workspace data
"""

from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter, Depends

from backend.core.logging import get_logger
from backend.core.security import get_admin_user
from backend.db.session import check_db_connection, redis_client, supabase


logger = get_logger("admin_routes")
router = APIRouter()


def _rows(table: str, columns: str = "*", limit: int | None = None) -> list[dict[str, Any]]:
    query = supabase.table(table).select(columns)
    if limit is not None:
        query = query.limit(limit)
    result = query.execute()
    return result.data or []


def _ordered_rows(
    table: str,
    columns: str = "*",
    *,
    order_by: str = "created_at",
    limit: int = 20,
    desc: bool = True,
) -> list[dict[str, Any]]:
    result = (
        supabase.table(table)
        .select(columns)
        .order(order_by, desc=desc)
        .limit(limit)
        .execute()
    )
    return result.data or []


def _costs_since(days: int) -> list[dict[str, Any]]:
    start_date = str(date.today() - timedelta(days=days))
    result = (
        supabase.table("ai_costs")
        .select("interview_id, model, call_type, cost_inr, tokens_in, tokens_out, latency_ms, created_at")
        .gte("created_at", start_date)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data or []


def _dashboard_payload() -> dict[str, Any]:
    interviews = _rows("interviews", "id, status, overall_score")
    total_interviews = len(interviews)
    completed = [item for item in interviews if item.get("status") == "completed"]
    scored_completed = [
        item for item in completed
        if isinstance(item.get("overall_score"), (int, float))
    ]
    avg_score = (
        sum(item["overall_score"] for item in scored_completed) / len(scored_completed)
        if scored_completed else 0
    )
    total_users = len(_rows("users", "id"))
    today_cost = sum(item.get("cost_inr", 0) for item in _costs_since(0))

    return {
        "total_interviews": total_interviews,
        "completed_interviews": len(completed),
        "average_score": round(avg_score, 1),
        "total_users": total_users,
        "today_cost_inr": round(today_cost, 2),
    }


def _cost_payload(days: int) -> dict[str, Any]:
    records = _costs_since(days)
    return {
        "days": days,
        "total_cost_inr": round(sum(item.get("cost_inr", 0) for item in records), 4),
        "total_tokens": sum(
            (item.get("tokens_in", 0) or 0) + (item.get("tokens_out", 0) or 0)
            for item in records
        ),
        "records": records,
    }


def _metrics_payload() -> dict[str, Any]:
    metrics: dict[str, Any] = {"status": "ok"}
    database = check_db_connection()
    metrics["database"] = database
    metrics["supabase_connected"] = database.get("supabase") == "ok"

    try:
        metrics["redis_connected"] = redis_client.ping()
        metrics["redis_memory"] = redis_client.info().get("used_memory_human", "unknown")
    except Exception as e:
        metrics["redis_connected"] = False
        metrics["redis_error"] = str(e)[:100]

    return metrics


@router.get("/me")
async def admin_me(user: dict = Depends(get_admin_user)):
    """Return the admin identity when access is allowed."""
    return {
        "is_admin": True,
        "email": user.get("email", ""),
        "user_id": user.get("sub", ""),
    }


@router.get("/dashboard")
async def admin_dashboard(_: dict = Depends(get_admin_user)):
    """Get admin dashboard KPIs."""
    return _dashboard_payload()


@router.get("/costs")
async def get_costs(days: int = 7, _: dict = Depends(get_admin_user)):
    """Get LLM cost breakdown for the last N days."""
    return _cost_payload(days)


@router.get("/metrics")
async def get_metrics(_: dict = Depends(get_admin_user)):
    """Get system-level metrics for monitoring."""
    return _metrics_payload()


@router.get("/overview")
async def admin_overview(_: dict = Depends(get_admin_user)):
    """Get the consolidated admin workspace payload."""
    return {
        "dashboard": _dashboard_payload(),
        "costs": _cost_payload(7),
        "metrics": _metrics_payload(),
        "recent_users": _ordered_rows(
            "users",
            "id, email, full_name, plan, difficulty_profile, created_at, updated_at",
            limit=20,
        ),
        "recent_interviews": _ordered_rows(
            "interviews",
            (
                "id, user_id, resume_id, job_role, interview_mode, status, "
                "overall_score, total_tokens, created_at, completed_at"
            ),
            limit=20,
        ),
        "latest_reports": _ordered_rows(
            "reports",
            "id, interview_id, overall_score, grade, interview_readiness, strengths, next_session_focus, created_at",
            limit=20,
        ),
    }
