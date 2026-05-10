"""Tests for API endpoints using TestClient."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock


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
        response = client.post(
            "/api/v1/resume/upload",
            files={"file": ("resume.pdf", b"dummy content", "application/pdf")}
        )
        assert response.status_code == 401

    @patch("backend.api.v1.routes.resume.supabase")
    def test_upload_invalid_file_type(self, mock_sb, client, auth_headers):
        """Resume upload with invalid file type should return 400."""
        response = client.post(
            "/api/v1/resume/upload",
            headers=auth_headers,
            files={"file": ("resume.txt", b"hello", "text/plain")},
        )
        assert response.status_code == 400


class TestAdminEndpoints:
    # Patch supabase exactly where it is used in admin.py
    @patch("backend.api.v1.routes.admin.supabase")
    def test_dashboard_returns_data(self, mock_sb, client):
        """Admin dashboard should return KPI data."""
        # Setup the mock to return empty lists so it doesn't crash
        mock_execute = MagicMock(data=[])
        mock_sb.table.return_value.select.return_value.execute.return_value = mock_execute
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_execute

        response = client.get("/api/v1/admin/dashboard")
        assert response.status_code == 200
        data = response.json()
        assert "total_interviews" in data
        assert data["total_interviews"] == 0