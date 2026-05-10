"""Tests for API endpoints using TestClient."""

import pytest
from fastapi.testclient import TestClient


class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        """Health endpoint should return status ok."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"


class TestAuthEndpoints:
    def test_signup_missing_fields(self, client, mock_supabase):
        """Signup with missing fields should return 422."""
        response = client.post("/api/v1/auth/signup", json={})
        assert response.status_code == 422

    def test_signup_invalid_email(self, client, mock_supabase):
        """Signup with invalid email should return 422."""
        response = client.post("/api/v1/auth/signup", json={
            "email": "not-an-email",
            "password": "password123",
        })
        assert response.status_code == 422

    def test_login_missing_fields(self, client, mock_supabase):
        """Login with missing fields should return 422."""
        response = client.post("/api/v1/auth/login", json={})
        assert response.status_code == 422


class TestResumeEndpoints:
    def test_upload_without_auth(self, client):
        """Resume upload without auth should return 401."""
        response = client.post("/api/v1/resume/upload")
        assert response.status_code == 401

    def test_upload_invalid_file_type(self, client, auth_headers):
        """Resume upload with invalid file type should return 400."""
        response = client.post(
            "/api/v1/resume/upload",
            headers=auth_headers,
            files={"file": ("resume.txt", b"hello", "text/plain")},
        )
        assert response.status_code == 400


class TestAdminEndpoints:
    def test_dashboard_returns_data(self, client, mock_supabase):
        """Admin dashboard should return KPI data."""
        response = client.get("/api/v1/admin/dashboard")
        assert response.status_code == 200
        data = response.json()
        assert "total_interviews" in data