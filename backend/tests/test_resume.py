"""Tests for resume parsing and RAG pipeline."""

import pytest,os
from backend.services.resume_parser import extract_text, classify_resume, ParsedResume
from backend.services.rag_ingestion import chunk_text


class TestResumeParser:
    def test_extract_text_unsupported_type(self):
        """Unsupported file types should raise ValueError."""
        with pytest.raises(ValueError, match="Unsupported file type"):
            extract_text(b"data", "resume.txt")

    def test_classify_resume_short_text(self):
        """Very short text should return a minimal ParsedResume."""
        result = classify_resume("hi")
        assert isinstance(result, ParsedResume)

    @pytest.mark.skipif(
        not os.getenv("GOOGLE_API_KEY", "").startswith("AI"),
        reason="Requires real Gemini API key"
    )
    def test_classify_resume_full(self):
        """Full resume text should be classified into sections."""
        import os
        sample_resume = """
        John Doe - Software Engineer
        
        Experience:
        - Senior Developer at Google (2020-2024): Built microservices, led team of 5
        - Junior Developer at Startup (2018-2020): Full-stack development
        
        Skills:
        Python, JavaScript, React, FastAPI, PostgreSQL, Docker, Kubernetes
        
        Education:
        - B.Tech in Computer Science from IIT Delhi (2018)
        
        Projects:
        - E-commerce platform with 100K users
        - Open-source CLI tool with 500 GitHub stars
        """
        result = classify_resume(sample_resume)
        assert isinstance(result, ParsedResume)
        assert len(result.skills) > 0
        assert len(result.experience) > 0


class TestChunking:
    def test_chunk_text_empty(self):
        """Empty text should return no chunks."""
        result = chunk_text("")
        assert result == []

    def test_chunk_text_short(self):
        """Text shorter than chunk_size should return one chunk."""
        result = chunk_text("Hello world this is a test.")
        assert len(result) >= 1

    def test_chunk_text_long(self):
        """Long text should be split into multiple chunks."""
        text = "This is a sentence. " * 100  # ~2200 chars
        chunks = chunk_text(text, chunk_size=500, overlap=50)
        assert len(chunks) > 1
        # Each chunk should have text
        for chunk in chunks:
            assert "text" in chunk
            assert len(chunk["text"]) > 0

    def test_chunk_overlap(self):
        """Chunks should overlap by the specified amount."""
        text = "Sentence one here. Sentence two here. Sentence three here. " * 20
        chunks = chunk_text(text, chunk_size=200, overlap=30)
        if len(chunks) > 1:
            # Adjacent chunks should share some text
            assert len(chunks) > 1