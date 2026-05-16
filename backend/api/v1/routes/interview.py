import uuid

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from pydantic import BaseModel

from ai.agents.generator import clean_job_description
from ai.personas.interviewer_personas import get_persona
from backend.core.logging import get_logger
from backend.core.security import get_current_user
from backend.services.interview.analysis import (
    analyze_audio_submission,
    analyze_frame_submission,
    summarize_behavior_for_user,
)
from backend.services.interview.completion import complete_interview_for_user
from backend.services.interview.repository import (
    create_interview_record,
    fetch_resume_for_user,
    fetch_questions_for_interview,
    get_interview_for_user,
    insert_question,
    list_interviews_for_user,
)
from backend.services.interview.realtime import (
    handle_websocket_frame,
    handle_websocket_text,
)
from backend.services.interview.session_state import (
    reset_interview_session,
    with_session_interview_context,
)
from backend.services.interview.starter import (
    build_starter_interview_plan,
    first_intro_question_payload,
)


logger = get_logger("interview_routes")

router = APIRouter(
    prefix="/interview",
    tags=["Interview"],
)

VALID_INTERVIEW_MODES = {"faang", "startup", "hr"}


class StartInterviewRequest(BaseModel):
    resume_id: str | None = None
    job_role: str = "General"
    job_description: str = ""
    interview_mode: str = "faang"


class CompleteInterviewRequest(BaseModel):
    overall_score: int | None = None
    behavior_summary: dict | None = None


@router.post("/start")
async def start_interview(
    req: StartInterviewRequest,
    user: dict = Depends(get_current_user),
):
    if req.interview_mode not in VALID_INTERVIEW_MODES:
        raise HTTPException(status_code=400, detail="Invalid interview mode")

    interview_id = str(uuid.uuid4())
    job_role = req.job_role.strip() or "General"
    job_description = clean_job_description(req.job_description)
    resume = None

    try:
        if req.resume_id:
            resume = fetch_resume_for_user(req.resume_id, user)
            if not resume:
                raise HTTPException(status_code=404, detail="Resume not found")

        created_interview = create_interview_record(
            interview_id=interview_id,
            user_id=user["sub"],
            resume_id=req.resume_id,
            job_role=job_role,
            job_description=job_description,
            interview_mode=req.interview_mode,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            "interview_create_failed",
            user_id=user.get("sub"),
            error=str(e),
        )
        raise HTTPException(status_code=500, detail="Unable to create interview")

    parsed_resume = (resume or {}).get("parsed_json") or {}
    if not isinstance(parsed_resume, dict):
        parsed_resume = {"summary": str(parsed_resume)}

    interview_plan = build_starter_interview_plan(
        job_role=created_interview["job_role"],
        interview_mode=req.interview_mode,
    )
    first_question_payload = first_intro_question_payload(
        interview_mode=req.interview_mode,
        job_role=created_interview["job_role"],
        job_description=created_interview["job_description"],
        interview_id=interview_id,
    )
    agent_state = {
        "user_id": user["sub"],
        "interview_id": interview_id,
        "resume_id": req.resume_id or "",
        "job_role": created_interview["job_role"],
        "job_description": created_interview["job_description"],
        "resume_summary": parsed_resume,
        "difficulty": "medium",
        "interview_plan": interview_plan,
        "questions": [first_question_payload],
        "answers": [],
        "evaluations": [],
        "speech_metrics": [],
        "behavior_data": [],
        "current_index": 0,
        "weak_topics": [],
        "strong_topics": [],
        "session_topic_scores": {},
        "interview_mode": req.interview_mode,
        "difficulty_profile": "beginner",
        "retrieved_chunks": [],
        "report": None,
    }

    reset_interview_session(
        interview_id,
        job_description=created_interview["job_description"],
        job_role=created_interview["job_role"],
        interview_mode=req.interview_mode,
        agent_state=agent_state,
    )

    first_question = insert_question(
        interview_id,
        first_question_payload,
    )
    persona = get_persona(req.interview_mode)

    return {
        "success": True,
        "interview_id": interview_id,
        "first_question": first_question,
        "persona_name": persona.get("name"),
        "opening_line": persona.get("opening_line"),
        "job_role": created_interview["job_role"],
        "job_description": created_interview["job_description"],
        "interview_mode": req.interview_mode,
        "resume_id": req.resume_id,
        "created_at": created_interview["created_at"],
    }


@router.get("/health")
async def health_check():
    return {
        "status": "ok",
        "service": "interview",
    }


@router.get("")
@router.get("/")
async def list_interviews(user: dict = Depends(get_current_user)):
    """List interview sessions owned by the current user."""
    return {"interviews": list_interviews_for_user(user)}


@router.post("/analyze-frame")
async def analyze_webcam_frame(
    interview_id: str = Form(...),
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    try:
        frame_bytes = await file.read()
        return await analyze_frame_submission(
            interview_id=interview_id,
            user=user,
            frame_bytes=frame_bytes,
            mime_type=file.content_type or "image/jpeg",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            "frame_analysis_failed",
            error=str(e),
        )
        return {
            "success": False,
            "error": str(e),
        }


@router.post("/analyze-audio")
async def analyze_audio_answer(
    interview_id: str = Form(...),
    question: str = Form(...),
    question_id: str | None = Form(None),
    duration_sec: float | None = Form(None),
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    try:
        audio_bytes = await file.read()
        return await analyze_audio_submission(
            interview_id=interview_id,
            user=user,
            question=question,
            question_id=question_id,
            duration_sec=duration_sec,
            audio_bytes=audio_bytes,
            mime_type=file.content_type or "audio/webm",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            "audio_analysis_failed",
            error=str(e),
        )
        return {
            "success": False,
            "error": str(e),
        }


@router.get("/behavior-summary/{interview_id}")
async def get_behavior_summary(
    interview_id: str,
    user: dict = Depends(get_current_user),
):
    try:
        return summarize_behavior_for_user(interview_id, user)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            "behavior_summary_failed",
            error=str(e),
        )
        return {
            "success": False,
            "error": str(e),
        }


@router.get("/{interview_id}")
async def get_interview_status(
    interview_id: str,
    user: dict = Depends(get_current_user),
):
    """Fetch an interview and its saved questions from Supabase."""
    interview = with_session_interview_context(
        interview_id,
        get_interview_for_user(interview_id, user),
    )
    return {
        "interview": interview,
        "questions": fetch_questions_for_interview(interview_id),
    }


@router.websocket("/ws/interview/{interview_id}")
async def realtime_interview_socket(
    websocket: WebSocket,
    interview_id: str,
):
    await websocket.accept()
    logger.info(
        "websocket_connected",
        interview_id=interview_id,
    )

    try:
        while True:
            data = await websocket.receive()

            if data.get("bytes") is not None:
                await handle_websocket_frame(websocket, interview_id, data["bytes"])
                continue

            if data.get("text") is not None:
                await handle_websocket_text(websocket, interview_id, data["text"])
    except WebSocketDisconnect:
        logger.info(
            "websocket_disconnected",
            interview_id=interview_id,
        )
    except Exception as e:
        logger.exception(
            "websocket_failed",
            error=str(e),
        )


@router.post("/{interview_id}/complete")
async def complete_interview(
    interview_id: str,
    req: CompleteInterviewRequest,
    user: dict = Depends(get_current_user),
):
    try:
        return complete_interview_for_user(
            interview_id=interview_id,
            user=user,
            overall_score=req.overall_score,
            behavior_summary=req.behavior_summary,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            "interview_complete_failed",
            interview_id=interview_id,
            error=str(e),
        )
        raise HTTPException(status_code=500, detail="Unable to complete interview")
