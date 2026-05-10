import uuid
from fastapi import APIRouter, UploadFile, File, HTTPException, status
from backend.services.resume_parser import extract_text, classify_resume
from backend.services.rag_ingestion import chunk_text, embed_and_store
from backend.db.session import supabase
from backend.core.security import decode_access_token
from backend.core.logging import get_logger

"""
Resume routes:
- POST /upload — Upload PDF/DOCX resume, parse, embed, store
- GET /{id} — Get parsed resume data
- DELETE /{id} — Delete resume and all chunks
"""

logger = get_logger("resume_routes")
router = APIRouter()

@router.post("/upload")
async def upload_resume(file : UploadFile = File(...),authorization : str = ""):
    """Upload a resume (PDF or DOCX), parse it, embed it, store in pgvector."""
    # Auth check
    if not authorization.startswith("Bearer"):
        raise HTTPException(status_code= 401,detail="Missing Token")
    
    payload = decode_access_token(authorization.replace("Bearer",""))
    user_id = payload["sub"]

    if not file.filename:
        raise HTTPException(status_code=400,
                            detail=f"Only {', '.join(allowed_types)} files are supported",
        )
    allowed_types = [".pdf", ".docx"]
    if not any(file.filename.lower().endswith(t) for t in allowed_types):
        raise HTTPException(
            status_code=400,
            detail=f"Only {', '.join(allowed_types)} files are supported",
        )
    # Read file
    file_bytes = await file.read()
    if len(file_bytes) > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(status_code=400, detail="File too large (max 10MB)")

    # Extract text
    try:
        raw_text = extract_text(file_bytes, file.filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if len(raw_text.strip()) < 50:
        raise HTTPException(status_code=400, detail="Resume appears empty or unreadable")

    # Classify sections
    parsed_resume = classify_resume(raw_text)

    # Create resume record
    resume_id = str(uuid.uuid4())
    supabase.table("resumes").insert({
        "id": resume_id,
        "user_id": user_id,
        "file_name": file.filename,
        "parsed_json": parsed_resume.model_dump(),
        "raw_text": raw_text[:5000],
    }).execute()

    # Chunk and embed
    chunks = chunk_text(raw_text)
    section_tags = []
    for chunk in chunks:
        text = chunk["text"].lower()
        if any(s.lower() in text for s in parsed_resume.skills):
            section_tags.append("skills")
        elif any(e.lower() in text for e in parsed_resume.experience):
            section_tags.append("experience")
        elif any(ed.lower() in text for ed in parsed_resume.education):
            section_tags.append("education")
        else:
            section_tags.append("general")

    stored = embed_and_store(resume_id, chunks, section_tags)

    logger.info(
        "resume_uploaded",
        resume_id=resume_id,
        chunks_stored=stored,
        user_id=user_id,
    )

    return {
        "resume_id": resume_id,
        "parsed": parsed_resume.model_dump(),
        "chunks_stored": stored,
        "message": "Resume processed successfully",
    }

@router.get("/{resume_id}")
async def get_resume(resume_id: str, authorization: str = ""):
    """Get parsed resume data."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")

    result = supabase.table("resumes").select("*").eq("id", resume_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Resume not found")

    return result.data[0]


@router.delete("/{resume_id}")
async def delete_resume(resume_id: str, authorization: str = ""):
    """Delete resume and all associated chunks."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")

    # Delete chunks first (cascade should handle this, but be explicit)
    supabase.table("resume_chunks").delete().eq("resume_id", resume_id).execute()
    supabase.table("resumes").delete().eq("id", resume_id).execute()

    logger.info("resume_deleted", resume_id=resume_id)
    return {"message": "Resume deleted successfully"}


