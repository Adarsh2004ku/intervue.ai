"""
PDF report generation using fpdf2.
Creates a professional-looking report with:
- Overall score and grade
- Per-topic breakdown
- Improvement plan
- Speech analysis
"""

from fpdf import FPDF
from backend.core.logging import get_logger

logger = get_logger("pdf_generator")


class InterviewReport(FPDF):
    """Custom PDF class for interview reports."""

    def header(self):
        self.set_font("Helvetica", "B", 12)
        self.cell(0, 10, "Intervue.AI — Interview Report", align="C", new_x="LMARGIN", new_y="NEXT")
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")


def generate_report_pdf(report: dict, interview: dict) -> bytes:
    """
    Generate a PDF report from interview data.
    Returns PDF bytes for streaming response.
    """
    pdf = InterviewReport()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=20)

    # Title
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 15, "Interview Report", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    # Basic info
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, f"Job Role: {interview.get('job_role', 'N/A')}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 8, f"Interview Mode: {interview.get('interview_mode', 'N/A').title()}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 8, f"Date: {interview.get('created_at', 'N/A')[:10]}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    # Overall Score
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, f"Overall Score: {report.get('overall_score', 0)}/100", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 10, f"Grade: {report.get('grade', 'N/A')}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 10, f"Interview Readiness: {report.get('interview_readiness', 'N/A').replace('_', ' ').title()}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    # Per-topic feedback
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 10, "Per-Topic Feedback", new_x="LMARGIN", new_y="NEXT")

    feedback = report.get("feedback_json", {})
    if isinstance(feedback, dict):
        for topic, details in feedback.items():
            pdf.set_font("Helvetica", "B", 11)
            pdf.cell(0, 8, f"  {topic}", new_x="LMARGIN", new_y="NEXT")
            if isinstance(details, dict):
                pdf.set_font("Helvetica", "", 10)
                for key, value in details.items():
                    pdf.cell(0, 6, f"    {key}: {value}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    # Improvement Plan
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 10, "Improvement Plan", new_x="LMARGIN", new_y="NEXT")

    plan = report.get("improvement_plan", [])
    if isinstance(plan, list):
        for item in plan:
            if isinstance(item, dict):
                pdf.set_font("Helvetica", "B", 11)
                pdf.cell(0, 8, f"  Priority {item.get('priority', '?')}: {item.get('topic', 'Unknown')}", new_x="LMARGIN", new_y="NEXT")
                pdf.set_font("Helvetica", "", 10)
                pdf.cell(0, 6, f"    Action: {item.get('action', 'N/A')}", new_x="LMARGIN", new_y="NEXT")
                pdf.cell(0, 6, f"    Resource: {item.get('resource', 'N/A')}", new_x="LMARGIN", new_y="NEXT")
                pdf.cell(0, 6, f"    Time: {item.get('estimated_time', 'N/A')}", new_x="LMARGIN", new_y="NEXT")
                pdf.cell(0, 6, f"    Why: {item.get('why', 'N/A')}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    # Strengths
    strengths = report.get("strengths", [])
    if strengths:
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 10, "Strengths", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        for s in strengths:
            pdf.cell(0, 6, f"  ✓ {s}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(5)

    # Next Session Focus
    focus = report.get("next_session_focus", [])
    if focus:
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 10, "Next Session Focus", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        for f in focus:
            pdf.cell(0, 6, f"  → {f}", new_x="LMARGIN", new_y="NEXT")

    # Output
    pdf_bytes = pdf.output()
    logger.info("pdf_generated", size_kb=len(pdf_bytes) // 1024)
    return bytes(pdf_bytes)