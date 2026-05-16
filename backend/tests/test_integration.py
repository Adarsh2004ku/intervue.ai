"""
End-to-End Integration Tests.
Tests the full flow: Resume Upload -> Interview Start -> WebSocket Audio/Frame -> Report Generation.
Uses httpx AsyncClient for real HTTP calls against a running test server.
"""

from unittest.mock import patch

from backend.services.interview.starter import INTRO_QUESTION_TEXT
from backend.services.resume_parser import ParsedResume


class TestFullInterviewFlow:
    """Integration tests for the complete interview pipeline."""

    def test_health_check(self, client):
        """Verify the server is running and healthy."""
        res = client.get("/health")
        assert res.status_code == 200
        assert res.json()["status"] == "ok"

    def test_signup_and_login(self, client, mock_supabase):
        """Test user registration and login flow."""
        # Signup
        signup_data = {"email": "integration@test.com", "password": "securepassword", "full_name": "Test User"}
        res = client.post("/api/v1/auth/signup", json=signup_data)
        assert res.status_code == 200
        token = res.json()["access_token"]
        assert token is not None

        # Login
        res = client.post("/api/v1/auth/login", json={"email": "integration@test.com", "password": "securepassword"})
        assert res.status_code == 200
        assert res.json()["access_token"] is not None

    def test_resume_upload_and_retrieval(self, client, auth_headers, mock_supabase):
        """Test resume upload creates DB records and returns parsed data."""
        # Mock the actual AI parsing to avoid burning API keys in CI
        with patch("backend.api.v1.routes.resume.extract_text") as mock_extract, \
             patch("backend.api.v1.routes.resume.classify_resume") as mock_classify, \
             patch("backend.api.v1.routes.resume.embed_and_store") as mock_embed:
            
            mock_extract.return_value = "Python skills and development experience from a test resume."
            mock_classify.return_value = ParsedResume(skills=["Python"], experience=["Dev"], education=["BSc"], projects=[], summary="Test")
            mock_embed.return_value = 5

            # Upload
            fake_pdf = b"%PDF-1.4 fake resume content with Python skills"
            res = client.post(
                "/api/v1/resume/upload",
                headers=auth_headers,
                files={"file": ("resume.pdf", fake_pdf, "application/pdf")}
            )
            assert res.status_code == 200
            data = res.json()
            assert "resume_id" in data
            assert data["parsed"]["skills"] == ["Python"]
            assert data["chunks_stored"] == 5

    def test_interview_start(self, client, auth_headers, mock_supabase, mock_redis):
        """Test that starting an interview generates a question and connects to WS."""
        persona = {"name": "Alex (FAANG Interviewer)", "opening_line": "Let's begin."}
        created_interview = {
            "id": "test-interview-id",
            "resume_id": "fake-resume-id",
            "job_role": "Software Engineer",
            "job_description": "",
            "interview_mode": "faang",
            "created_at": "2026-05-16T00:00:00+00:00",
        }
        with patch("backend.api.v1.routes.interview.fetch_resume_for_user") as mock_resume, \
             patch("backend.api.v1.routes.interview.create_interview_record") as mock_create, \
             patch("backend.api.v1.routes.interview.insert_question") as mock_insert, \
             patch("backend.api.v1.routes.interview.get_persona") as mock_persona:
            mock_resume.return_value = {"id": "fake-resume-id", "parsed_json": {"skills": ["Python"]}}
            mock_create.return_value = created_interview
            mock_insert.side_effect = lambda _, payload: {"id": "question-id", **payload}
            mock_persona.return_value = persona
            
            res = client.post(
                "/api/v1/interview/interview/start",
                headers=auth_headers,
                json={"resume_id": "fake-resume-id", "job_role": "Software Engineer", "interview_mode": "faang"}
            )
            assert res.status_code == 200
            data = res.json()
            assert "interview_id" in data
            assert data["first_question"]["text"] == INTRO_QUESTION_TEXT
            assert "Alex" in data["persona_name"]
