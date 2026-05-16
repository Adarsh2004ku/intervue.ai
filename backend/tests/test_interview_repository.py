from types import SimpleNamespace

from backend.services.interview import repository


class _CreateInterviewFallbackTable:
    def __init__(self):
        self.insert_payloads = []

    def insert(self, payload):
        self.insert_payloads.append(payload)
        return self

    def execute(self):
        if len(self.insert_payloads) == 1:
            raise Exception(
                "Could not find the 'job_description' column of 'interviews' "
                "in the schema cache (PGRST204)"
            )
        return SimpleNamespace(
            data=[
                {
                    "id": self.insert_payloads[-1]["id"],
                    "resume_id": self.insert_payloads[-1]["resume_id"],
                    "job_role": self.insert_payloads[-1]["job_role"],
                    "interview_mode": self.insert_payloads[-1]["interview_mode"],
                    "created_at": "2026-05-16T00:00:00+00:00",
                }
            ]
        )


class _CreateInterviewFallbackSupabase:
    def __init__(self):
        self.table_query = _CreateInterviewFallbackTable()

    def table(self, name):
        assert name == "interviews"
        return self.table_query


def test_create_interview_retries_legacy_schema_without_losing_job_description(monkeypatch):
    fake_supabase = _CreateInterviewFallbackSupabase()
    monkeypatch.setattr(repository, "supabase", fake_supabase)

    row = repository.create_interview_record(
        interview_id="interview-1",
        user_id="user-1",
        resume_id=None,
        job_role="Backend Engineer",
        job_description="Build FastAPI services and own PostgreSQL schemas.",
        interview_mode="faang",
    )

    assert fake_supabase.table_query.insert_payloads[0]["job_description"]
    assert "job_description" not in fake_supabase.table_query.insert_payloads[1]
    assert row["job_description"] == "Build FastAPI services and own PostgreSQL schemas."
