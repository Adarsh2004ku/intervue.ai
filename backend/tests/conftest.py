"""
Pytest configuration and shared fixtures.
Provides test client, mock database, and mock LLM responses.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

# Patch settings before importing app
import os
os.environ.setdefault("GOOGLE_API_KEY", "test-key")
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-key")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "test-service-key")
os.environ.setdefault("JWT_SECRET", "test-secret-32-characters-minimum")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")


@pytest.fixture
def client():
    """FastAPI test client."""
    from backend.main import app
    return TestClient(app)


@pytest.fixture
def mock_supabase():
    """Mock Supabase client for testing."""
    with patch("backend.db.session.supabase") as mock_sb:
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": "test-uuid", "email": "test@test.com"}]
        )
        mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[{"id": "test-uuid"}]
        )
        mock_sb.table.return_value.delete.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[]
        )
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