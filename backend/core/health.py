from typing import Any

from backend.core.config import settings
from backend.db.session import check_db_connection


def build_health_payload() -> dict[str, Any]:
    return {
        "status": "ok",
        "version": "1.0.0",
        "environment": settings.environment,
        "database": check_db_connection(),
    }
