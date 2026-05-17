"""
Pytest configuration and shared fixtures.
Provides test client, mock database, and mock LLM responses.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from types import SimpleNamespace

# Patch settings before importing app
import os

@pytest.fixture
def client():
    """FastAPI test client."""
    from backend.main import app
    return TestClient(app)


@pytest.fixture(autouse=True)
def disable_celery_for_tests(monkeypatch):
    """Keep tests inline unless a test explicitly enables Celery."""
    from backend.core.config import settings

    monkeypatch.setattr(settings, "celery_enabled", False)
    monkeypatch.setattr(settings, "celery_task_always_eager", False)

@pytest.fixture
def mock_supabase():
    """Mock Supabase client for testing."""
    with patch("backend.db.session.supabase") as mock_sb, \
         patch("backend.api.v1.routes.auth.get_supabase_client") as mock_auth_client, \
         patch("backend.api.v1.routes.resume.supabase", mock_sb), \
         patch("backend.api.v1.routes.admin.supabase", mock_sb), \
         patch("backend.services.interview.repository.supabase", mock_sb), \
         patch("backend.services.interview.topic_profile.supabase", mock_sb), \
         patch("backend.services.reports.builder.supabase", mock_sb):
        # Flexible mock that handles both .eq() and non-.eq() chains
        mock_execute = MagicMock(data=[])
        mock_insert_execute = MagicMock(data=[{"id": "test-uuid", "email": "test@test.com"}])
        auth_user = SimpleNamespace(
            id="test-user-id",
            email="test@test.com",
            user_metadata={},
        )
        
        mock_sb.auth.admin.create_user.return_value = SimpleNamespace(user=auth_user)
        mock_sb.auth.sign_in_with_password.return_value = SimpleNamespace(user=auth_user)
        mock_sb.table.return_value.select.return_value.execute.return_value = mock_execute
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_execute
        mock_sb.table.return_value.insert.return_value.execute.return_value = mock_insert_execute
        mock_sb.table.return_value.upsert.return_value.execute.return_value = mock_insert_execute
        mock_sb.table.return_value.delete.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        mock_auth_client.return_value = mock_sb
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
