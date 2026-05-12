"""
Pytest configuration and shared fixtures.
Provides test client, mock database, and mock LLM responses.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from contextlib import ExitStack

# Patch settings before importing app
import os

@pytest.fixture
def client():
    """FastAPI test client."""
    from backend.main import app
    return TestClient(app)

@pytest.fixture
def mock_supabase():
    """Mock Supabase client for testing."""
    mock_sb = MagicMock()
    table = mock_sb.table.return_value
    for method in [
        "select",
        "insert",
        "upsert",
        "delete",
        "update",
        "eq",
        "lt",
        "gte",
        "order",
        "limit",
        "single",
        "in_",
    ]:
        getattr(table, method).return_value = table
    table.execute.return_value = MagicMock(data=[])

    auth_user = MagicMock(id="test-user-id", email="test@test.com", user_metadata={"full_name": "Test User"})
    mock_sb.auth.admin.create_user.return_value = MagicMock(user=auth_user)
    mock_sb.auth.sign_in_with_password.return_value = MagicMock(user=auth_user)
    mock_sb.auth.get_user.return_value = MagicMock(user=auth_user)

    patch_targets = [
        "backend.db.session.supabase",
        "backend.api.v1.routes.auth.supabase",
        "backend.api.v1.routes.resume.supabase",
        "backend.api.v1.routes.admin.supabase",
        "backend.api.v1.routes.report.supabase",
        "backend.services.cost_tracking.supabase",
        "backend.services.interview_agent_flow.supabase",
        "ai.agents.planner.supabase",
        "ai.agents.coach.supabase",
    ]

    with ExitStack() as stack:
        for target in patch_targets:
            stack.enter_context(patch(target, mock_sb))
        yield mock_sb


@pytest.fixture
def mock_redis():
    """Mock Redis client for testing."""
    with patch("backend.db.session.redis_client") as mock_r:
        mock_r.ping.return_value = True
        mock_r.get.return_value = None
        mock_r.setex.return_value = True
        yield mock_r


@pytest.fixture
def auth_token():
    """Generate a valid JWT token for testing."""
    from backend.core.security import create_access_token
    return create_access_token({"sub": "test-user-id", "email": "test@test.com"})


@pytest.fixture
def auth_headers(auth_token):
    """Authorization headers with valid JWT."""
    return {"Authorization": f"Bearer {auth_token}"}
