"""Tests for API endpoints using TestClient."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from types import SimpleNamespace


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

    def test_signup_duplicate_email_returns_conflict(self, client, mock_supabase):
        """Duplicate Supabase users should return a client error, not a 500."""
        mock_supabase.auth.admin.create_user.side_effect = Exception(
            "A user with this email address has already been registered"
        )

        response = client.post("/api/v1/auth/signup", json={
            "email": "duplicate@test.com",
            "password": "password123",
            "full_name": "Duplicate User",
        })

        assert response.status_code == 409
        assert response.json()["detail"] == "Email already registered"

    def test_login_missing_fields(self, client, mock_supabase):
        """Login with missing fields should return 422."""
        response = client.post("/api/v1/auth/login", json={})
        assert response.status_code == 422

    def test_google_oauth_callback_exchanges_auth_code(self, client, mock_supabase):
        """OAuth callback should exchange Supabase auth_code and redirect with app token."""
        auth_user = SimpleNamespace(
            id="oauth-user-id",
            email="oauth@test.com",
            user_metadata={"full_name": "OAuth User"},
        )
        mock_supabase.auth.exchange_code_for_session.return_value = SimpleNamespace(user=auth_user)

        response = client.get(
            "/api/v1/auth/callback?code=test-code",
            follow_redirects=False,
        )

        assert response.status_code == 307
        mock_supabase.auth.exchange_code_for_session.assert_called_once_with({"auth_code": "test-code"})
        assert response.headers["location"].startswith("http://localhost:3000/auth/callback?access_token=")


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

    def test_upload_queues_embeddings_when_celery_enabled(
        self,
        client,
        auth_headers,
        mock_supabase,
        monkeypatch,
    ):
        """Resume upload should return immediately after queueing embeddings."""
        from backend.core.config import settings
        from backend.services.resume_parser import ParsedResume

        monkeypatch.setattr(settings, "celery_enabled", True)
        monkeypatch.setattr(settings, "celery_task_always_eager", False)

        with patch("backend.api.v1.routes.resume.extract_text") as mock_extract, \
             patch("backend.api.v1.routes.resume.classify_resume") as mock_classify, \
             patch("backend.api.v1.routes.resume.embed_and_store") as mock_embed, \
             patch("backend.api.v1.routes.resume.embed_resume_chunks_task.apply_async") as mock_apply:
            mock_extract.return_value = (
                "Python backend development experience with APIs, databases, "
                "testing, reliability, and production debugging."
            )
            mock_classify.return_value = ParsedResume(
                skills=["Python"],
                experience=["backend development"],
                education=[],
                projects=[],
                summary="Backend developer",
            )
            mock_apply.return_value = SimpleNamespace(id="embedding-task-id")

            response = client.post(
                "/api/v1/resume/upload",
                headers=auth_headers,
                files={"file": ("resume.pdf", b"%PDF-1.4 fake resume content", "application/pdf")},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["embedding_status"] == "queued"
        assert data["embedding_task_id"] == "embedding-task-id"
        assert data["chunks_stored"] == 0
        mock_apply.assert_called_once()
        mock_embed.assert_not_called()

    def test_embedding_task_status_requires_owned_resume(self, client, auth_headers, mock_supabase):
        """Embedding task status should only be visible for the resume owner."""
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": "resume-id", "user_id": "test-user-id"}]
        )

        with patch("backend.api.v1.routes.resume.get_celery_task_status") as mock_status:
            mock_status.return_value = {
                "task_id": "embedding-task-id",
                "status": "success",
                "ready": True,
                "successful": True,
                "failed": False,
                "result": {"resume_id": "resume-id", "chunks_stored": 4},
            }

            response = client.get(
                "/api/v1/resume/resume-id/embedding-tasks/embedding-task-id",
                headers=auth_headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["embedding_status"] == "completed"
        assert data["chunks_stored"] == 4


class TestAdminEndpoints:
    # Patch supabase exactly where it is used in admin.py
    @patch("backend.api.v1.routes.admin.supabase")
    def test_dashboard_returns_data(self, mock_sb, client, auth_headers, monkeypatch):
        """Admin dashboard should return KPI data."""
        from backend.core.config import settings

        monkeypatch.setattr(settings, "admin_emails", "test@test.com")
        # Setup the mock to return empty lists so it doesn't crash
        mock_execute = MagicMock(data=[])
        mock_sb.table.return_value.select.return_value.execute.return_value = mock_execute
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_execute

        response = client.get("/api/v1/admin/dashboard", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "total_interviews" in data
        assert data["total_interviews"] == 0

    def test_dashboard_rejects_non_admin(self, client, auth_headers, monkeypatch):
        """Admin dashboard should reject authenticated non-admin users."""
        from backend.core.config import settings

        monkeypatch.setattr(settings, "admin_emails", "owner@test.com")
        response = client.get("/api/v1/admin/dashboard", headers=auth_headers)
        assert response.status_code == 403
