import io
import json
import re

from pydantic import BaseModel, Field
from backend.services.llm.provider import get_gemini_direct, parse_llm_json
from backend.core.logging import get_logger

logger = get_logger("resume_parser")
"""
Resume parsing pipeline:
1. Extract raw text from PDF or DOCX
2. Use LLM to classify sections (experience, skills, education, projects, summary)
3. Return structured ParsedResume object
"""

class ParsedResume(BaseModel):
    """Structured output from resume parsing."""
    experience: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)
    projects: list[str] = Field(default_factory=list)
    summary: str = ""


def _extract_section(raw_text: str, names: list[str]) -> list[str]:
    labels = ["experience", "skills", "education", "projects", "summary"]
    pattern = "|".join(re.escape(label) for label in labels)
    for name in names:
      match = re.search(
          rf"{name}\s*:?\s*(.*?)(?=\n\s*(?:{pattern})\s*:|\Z)",
          raw_text,
          flags=re.IGNORECASE | re.DOTALL,
      )
      if match:
          lines = [
              re.sub(r"^[\-\*\u2022]\s*", "", line.strip())
              for line in match.group(1).splitlines()
              if line.strip()
          ]
          return lines
    return []


def _heuristic_parse(raw_text: str) -> ParsedResume:
    skills = []
    skill_lines = _extract_section(raw_text, ["skills", "technical skills"])
    for line in skill_lines:
        skills.extend([item.strip() for item in re.split(r",|\|", line) if item.strip()])

    experience = _extract_section(raw_text, ["experience", "work experience", "employment"])
    education = _extract_section(raw_text, ["education"])
    projects = _extract_section(raw_text, ["projects", "project"])

    return ParsedResume(
        experience=experience[:8],
        skills=skills[:30],
        education=education[:6],
        projects=projects[:8],
        summary=" ".join(raw_text.split())[:500],
    )


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract text from a PDF file using PyPDF2."""
    import PyPDF2

    reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
    pages = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text)
    return "\n\n".join(pages)


def extract_text_from_docx(file_bytes: bytes) -> str:
    """Extract text from a DOCX file using python-docx."""
    import docx

    doc = docx.Document(io.BytesIO(file_bytes))
    return "\n".join(para.text for para in doc.paragraphs if para.text.strip())


def extract_text(file_bytes: bytes, filename: str) -> str:
    """Extract raw text based on file extension."""
    filename_lower = filename.lower()
    if filename_lower.endswith(".pdf"):
        return extract_text_from_pdf(file_bytes)
    elif filename_lower.endswith(".docx"):
        return extract_text_from_docx(file_bytes)
    else:
        raise ValueError(f"Unsupported file type: {filename}. Only PDF and DOCX are supported.")


def classify_resume(raw_text: str) -> ParsedResume:
    """
    Use LLM to classify resume text into structured sections.
    Returns a ParsedResume object with categorized content.
    """
    if len(raw_text.strip()) < 50:
        logger.warning("resume_too_short", length=len(raw_text))
        return ParsedResume(summary="Resume content too short to parse")

    llm = get_gemini_direct(temperature=0.1)

    prompt = f"""You are a resume parser. Analyze the following resume text and extract 
structured information.

Return ONLY valid JSON with these keys:
- "experience": list of strings, each describing a work experience
- "skills": list of strings, each a technical or soft skill
- "education": list of strings, each describing an educational qualification
- "projects": list of strings, each describing a project
- "summary": a 2-3 sentence professional summary

Resume Text:
{raw_text[:8000]}

Return ONLY the JSON object, no markdown, no explanation."""

    try:
        response = llm.invoke(prompt)
        parsed_data = parse_llm_json(response.content)
        return ParsedResume(**parsed_data)

    except (json.JSONDecodeError, Exception) as e:
        logger.error("resume_classification_failed", error=str(e))
        return _heuristic_parse(raw_text)
