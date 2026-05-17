"""
Branded PDF report generation using fpdf2.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fpdf import FPDF

from backend.core.logging import get_logger


logger = get_logger("pdf_generator")


PAGE_W = 210
MARGIN = 14
CONTENT_W = PAGE_W - (MARGIN * 2)
PURPLE = (124, 58, 237)
INK = (31, 31, 40)
MUTED = (112, 112, 123)
LINE = (225, 225, 235)
SOFT = (246, 244, 255)
GREEN = (15, 118, 110)
ROSE = (190, 18, 60)


def _clean(value: Any, fallback: str = "N/A") -> str:
    text = fallback if value is None else str(value)
    text = (
        text.replace("\u2014", "-")
        .replace("\u2013", "-")
        .replace("\u2018", "'")
        .replace("\u2019", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2022", "-")
        .replace("\u2713", "OK")
        .replace("\u2192", "->")
    )
    return text.encode("latin-1", "replace").decode("latin-1")


def _date_label(value: Any) -> str:
    if not value:
        return "N/A"
    text = str(value)
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).strftime("%b %d, %Y")
    except ValueError:
        return text[:10]


def _readiness(value: Any) -> str:
    return _clean(value, "pending").replace("_", " ").title()


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _behavior_summary(report: dict[str, Any]) -> dict[str, Any]:
    speech_summary = report.get("speech_summary")
    if not isinstance(speech_summary, dict):
        return {}
    behavior = speech_summary.get("behavior_summary")
    return behavior if isinstance(behavior, dict) else {}


def _feedback(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    feedback = report.get("feedback_json")
    if not isinstance(feedback, dict):
        return {}
    return {
        str(topic): details
        for topic, details in feedback.items()
        if isinstance(details, dict)
    }


def _score(value: Any) -> int:
    try:
        return max(0, min(100, round(float(value))))
    except (TypeError, ValueError):
        return 0


def _average(values: list[int]) -> int:
    values = [value for value in values if value > 0]
    return round(sum(values) / len(values)) if values else 0


class InterviewReport(FPDF):
    """Custom PDF class for interview reports."""

    def header(self) -> None:
        self.set_fill_color(*PURPLE)
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 12)
        self.cell(13, 10, "ia", border=0, align="C", fill=True)
        self.set_x(30)
        self.set_text_color(*INK)
        self.set_font("Helvetica", "B", 15)
        self.cell(0, 10, "intervue.ai", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*LINE)
        self.line(MARGIN, self.get_y() + 1, PAGE_W - MARGIN, self.get_y() + 1)
        self.ln(8)

    def footer(self) -> None:
        self.set_y(-15)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*MUTED)
        self.cell(0, 10, f"intervue.ai interview report - Page {self.page_no()}", align="C")


def _section(pdf: InterviewReport, title: str) -> None:
    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(*INK)
    pdf.cell(0, 8, _clean(title), new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(*LINE)
    pdf.line(MARGIN, pdf.get_y(), PAGE_W - MARGIN, pdf.get_y())
    pdf.ln(4)


def _label_value(pdf: InterviewReport, label: str, value: Any, width: float = CONTENT_W / 2) -> None:
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*MUTED)
    pdf.cell(width, 5, _clean(label).upper(), new_x="LEFT", new_y="NEXT")
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*INK)
    pdf.multi_cell(width, 6, _clean(value), new_x="RIGHT", new_y="TOP")


def _pill(pdf: InterviewReport, text: Any, tone: tuple[int, int, int] = PURPLE) -> None:
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*tone)
    label = _clean(text)
    pill_w = min(max(pdf.get_string_width(label) + 8, 24), CONTENT_W)
    if pdf.get_x() + pill_w > PAGE_W - MARGIN:
        pdf.ln(8)
        pdf.set_x(MARGIN)
    pdf.set_fill_color(*SOFT)
    pdf.cell(pill_w, 7, label, border=0, align="C", fill=True)
    pdf.cell(3, 7, "")


def _write_wrapped(pdf: InterviewReport, text: Any, size: int = 10, color: tuple[int, int, int] = INK) -> None:
    pdf.set_font("Helvetica", "", size)
    pdf.set_text_color(*color)
    pdf.multi_cell(0, 5.5, _clean(text), new_x="LMARGIN", new_y="NEXT")


def _summary_cards(pdf: InterviewReport, report: dict[str, Any], interview: dict[str, Any]) -> None:
    pdf.set_fill_color(248, 249, 252)
    pdf.rect(MARGIN, pdf.get_y(), CONTENT_W, 48, "F")
    y = pdf.get_y() + 7
    pdf.set_xy(MARGIN + 7, y)
    _label_value(pdf, "Overall Score", f"{report.get('overall_score', 0)}/100", 42)
    pdf.set_xy(MARGIN + 53, y)
    _label_value(pdf, "Grade", report.get("grade", "N/A"), 32)
    pdf.set_xy(MARGIN + 89, y)
    _label_value(pdf, "Readiness", _readiness(report.get("interview_readiness")), 48)
    pdf.set_xy(MARGIN + 141, y)
    _label_value(pdf, "Questions", len(_feedback(report)), 36)
    pdf.set_xy(MARGIN + 7, y + 23)
    _label_value(pdf, "Role", interview.get("job_role", "N/A"), 74)
    pdf.set_xy(MARGIN + 87, y + 23)
    _label_value(pdf, "Mode", str(interview.get("interview_mode", "N/A")).title(), 44)
    pdf.set_xy(MARGIN + 137, y + 23)
    _label_value(pdf, "Date", _date_label(interview.get("completed_at") or interview.get("created_at")), 38)
    pdf.set_y(y + 46)


def _topics(pdf: InterviewReport, report: dict[str, Any]) -> None:
    feedback = _feedback(report)
    strong = [
        topic
        for topic, details in feedback.items()
        if _score(details.get("score")) >= 75
    ]
    weak = [
        topic
        for topic, details in feedback.items()
        if _score(details.get("score")) < 70
    ]
    strengths = [topic for topic in _as_list(report.get("strengths")) if topic != "Completed a live mock interview"]
    focus = _as_list(report.get("next_session_focus"))

    _section(pdf, "Topic Snapshot")
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*GREEN)
    pdf.cell(0, 6, "Strong topics", new_x="LMARGIN", new_y="NEXT")
    for topic in (strengths or strong or ["No strong topic recorded yet"])[:6]:
        _pill(pdf, topic, GREEN)
    pdf.ln(10)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*ROSE)
    pdf.cell(0, 6, "Weak topics / next focus", new_x="LMARGIN", new_y="NEXT")
    for topic in (weak or focus or ["No weak topic recorded yet"])[:6]:
        _pill(pdf, topic, ROSE)
    pdf.ln(8)


def _question_feedback(pdf: InterviewReport, report: dict[str, Any]) -> None:
    feedback = _feedback(report)
    _section(pdf, "Questions And Feedback")
    if not feedback:
        _write_wrapped(pdf, "No answer feedback was saved for this interview.", color=MUTED)
        return

    for index, (topic, details) in enumerate(feedback.items(), start=1):
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*PURPLE)
        pdf.multi_cell(0, 5.5, _clean(f"Q{index}. {details.get('question') or topic}"), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*INK)
        pdf.cell(
            0,
            5,
            _clean(
                f"Topic: {topic} | Score: {_score(details.get('score'))}/100 | "
                f"Accuracy: {_score(details.get('accuracy'))} | "
                f"Clarity: {_score(details.get('clarity'))} | Depth: {_score(details.get('depth'))}"
            ),
            new_x="LMARGIN",
            new_y="NEXT",
        )
        _write_wrapped(
            pdf,
            details.get("reasoning") or "No detailed feedback was saved for this answer.",
            size=9,
            color=MUTED,
        )
        pdf.ln(2)


def _improvement_plan(pdf: InterviewReport, report: dict[str, Any]) -> None:
    plan = _as_list(report.get("improvement_plan"))
    _section(pdf, "Improvement Plan")
    if not plan:
        _write_wrapped(pdf, "No improvement plan was saved for this report.", color=MUTED)
        return

    for item in plan[:5]:
        if not isinstance(item, dict):
            continue
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*INK)
        pdf.multi_cell(
            0,
            5.5,
            _clean(f"Priority {item.get('priority', '?')}: {item.get('topic', 'Unknown')}"),
            new_x="LMARGIN",
            new_y="NEXT",
        )
        _write_wrapped(pdf, f"Action: {item.get('action', 'N/A')}", size=9, color=MUTED)
        _write_wrapped(pdf, f"Resource: {item.get('resource', 'N/A')}", size=9, color=MUTED)
        _write_wrapped(pdf, f"Estimated time: {item.get('estimated_time', 'N/A')}", size=9, color=MUTED)
        pdf.ln(2)


def _speech_and_behavior(pdf: InterviewReport, report: dict[str, Any]) -> None:
    speech = report.get("speech_summary") if isinstance(report.get("speech_summary"), dict) else {}
    behavior = _behavior_summary(report)
    behavior_score = _average([
        _score(behavior.get("overall_engagement")),
        _score(behavior.get("overall_confidence")),
        _score(behavior.get("overall_professionalism")),
    ])

    _section(pdf, "Speech And Behaviour")
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*INK)
    pdf.cell(0, 6, _clean(f"Answers analyzed: {speech.get('answer_count', 0)}"), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, _clean(f"Average clarity: {_score(speech.get('average_clarity'))}/100"), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, _clean(f"Behaviour score: {behavior_score}/100"), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, _clean(f"Engagement: {_score(behavior.get('overall_engagement'))}/100"), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, _clean(f"Confidence: {_score(behavior.get('overall_confidence'))}/100"), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, _clean(f"Professionalism: {_score(behavior.get('overall_professionalism'))}/100"), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, _clean(f"Nervousness: {_score(behavior.get('overall_nervousness'))}/100"), new_x="LMARGIN", new_y="NEXT")
    _write_wrapped(
        pdf,
        behavior.get("behavior_summary") or "No behaviour summary was saved for this interview.",
        size=9,
        color=MUTED,
    )


def generate_report_pdf(report: dict, interview: dict) -> bytes:
    """
    Generate a branded PDF report from interview data.
    Returns PDF bytes for streaming response.
    """
    pdf = InterviewReport()
    pdf.set_title("intervue.ai interview report")
    pdf.set_author("intervue.ai")
    pdf.set_creator("intervue.ai")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    pdf.set_text_color(*INK)
    pdf.set_font("Helvetica", "B", 22)
    pdf.cell(0, 11, "Interview Report", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*MUTED)
    pdf.multi_cell(
        0,
        5.5,
        "A complete summary of score, readiness, questions, feedback, strengths, weak topics, and behaviour signals.",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.ln(3)

    _summary_cards(pdf, report, interview)
    _topics(pdf, report)
    _question_feedback(pdf, report)
    _improvement_plan(pdf, report)
    _speech_and_behavior(pdf, report)

    pdf_bytes = pdf.output()
    logger.info("pdf_generated", size_kb=len(pdf_bytes) // 1024)
    return bytes(pdf_bytes)
