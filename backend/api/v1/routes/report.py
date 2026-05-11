"""
Report routes:
- GET /{interview_id} — Get full report JSON
- GET /{interview_id}/pdf — Download PDF report
"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from backend.db.session import supabase
from backend.services.reports.pdf_generator import generate_report_pdf
from backend.core.security import get_current_user
from backend.core.logging import get_logger

logger = get_logger("report_routes")
router = APIRouter()


@router.get("/{interview_id}")
async def get_report(interview_id: str, user: dict = Depends(get_current_user)):
    """Get the full interview report as JSON."""
    interview_result = supabase.table("interviews").select("id").eq(
        "id", interview_id
    ).eq("user_id", user["sub"]).execute()

    if not interview_result.data:
        raise HTTPException(status_code=404, detail="Interview not found")

    result = supabase.table("reports").select("*").eq(
        "interview_id", interview_id
    ).execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="Report not found")

    return result.data[0]


@router.get("/{interview_id}/pdf")
async def get_report_pdf(interview_id: str, user: dict = Depends(get_current_user)):
    """Download the interview report as a PDF file."""
    interview_result = supabase.table("interviews").select("*").eq(
        "id", interview_id
    ).eq("user_id", user["sub"]).execute()

    if not interview_result.data:
        raise HTTPException(status_code=404, detail="Interview not found")

    # Fetch report data
    report_result = supabase.table("reports").select("*").eq(
        "interview_id", interview_id
    ).execute()

    if not report_result.data:
        raise HTTPException(status_code=404, detail="Report not found")

    interview = interview_result.data[0]

    # Generate PDF
    pdf_bytes = generate_report_pdf(report_result.data[0], interview)

    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=intervue-report-{interview_id[:8]}.pdf"
        },
    )
