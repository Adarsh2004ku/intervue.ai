"""
Report routes:
- GET /{interview_id} — Get full report JSON
- GET /{interview_id}/pdf — Download PDF report
"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from backend.db.session import supabase
from backend.services.reports import build_report_payload
from backend.services.reports.pdf_generator import generate_report_pdf
from backend.core.security import get_current_user
from backend.core.logging import get_logger

logger = get_logger("report_routes")
router = APIRouter()


def _first_behavior_summary(interview: dict) -> dict | None:
    notes = interview.get("behavior_notes")
    if isinstance(notes, list) and notes and isinstance(notes[0], dict):
        return notes[0]
    if isinstance(notes, dict):
        return notes
    return None


def _get_or_create_report(interview: dict) -> dict:
    report_result = supabase.table("reports").select("*").eq(
        "interview_id", interview["id"]
    ).execute()

    if report_result.data:
        return report_result.data[0]

    if interview.get("status") != "completed":
        raise HTTPException(status_code=404, detail="Report not found")

    report_payload = build_report_payload(
        interview=interview,
        requested_score=interview.get("overall_score"),
        behavior_summary=_first_behavior_summary(interview),
    )
    saved = supabase.table("reports").upsert(
        report_payload,
        on_conflict="interview_id",
    ).execute()
    return saved.data[0] if saved.data else report_payload


@router.get("/{interview_id}")
async def get_report(interview_id: str, user: dict = Depends(get_current_user)):
    """Get the full interview report as JSON."""
    interview_result = supabase.table("interviews").select("*").eq(
        "id", interview_id
    ).eq("user_id", user["sub"]).execute()

    if not interview_result.data:
        raise HTTPException(status_code=404, detail="Interview not found")

    return _get_or_create_report(interview_result.data[0])


@router.get("/{interview_id}/pdf")
async def get_report_pdf(interview_id: str, user: dict = Depends(get_current_user)):
    """Download the interview report as a PDF file."""
    interview_result = supabase.table("interviews").select("*").eq(
        "id", interview_id
    ).eq("user_id", user["sub"]).execute()

    if not interview_result.data:
        raise HTTPException(status_code=404, detail="Interview not found")

    interview = interview_result.data[0]
    report = _get_or_create_report(interview)

    # Generate PDF
    pdf_bytes = generate_report_pdf(report, interview)

    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=intervue-report-{interview_id[:8]}.pdf"
        },
    )
