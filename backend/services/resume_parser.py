import io
import json
from typing import Optional

from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field
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

    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.1)

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
        content = response.content.strip()

        # Strip markdown code fences if present
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]

        parsed_data = json.loads(content.strip())
        return ParsedResume(**parsed_data)

    except (json.JSONDecodeError, Exception) as e:
        logger.error("resume_classification_failed", error=str(e))
        # Fallback: return raw text as summary
        return ParsedResume(summary=raw_text[:500])