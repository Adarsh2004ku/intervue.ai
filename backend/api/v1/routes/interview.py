import json
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import (
    APIRouter,
    Depends,
    WebSocket,
    WebSocketDisconnect,
    UploadFile,
    File,
    Form,
    HTTPException,
)
from pydantic import BaseModel

from backend.core.config import settings
from backend.core.logging import (
    get_logger,
)
from backend.core.security import get_current_user
from backend.db.session import supabase
from backend.services.cost_tracking import (
    estimate_elevenlabs_stt_cost_inr,
    estimate_elevenlabs_tts_cost_inr,
    estimate_gemini_cost_inr,
    get_interview_cost_summary,
    record_ai_cost,
)

from backend.services.audio.gemini_stt import (
    transcribe_and_evaluate,
)
from backend.services.audio.elevenlabs_tts import (
    synthesize_interviewer_speech,
)

from backend.services.vision.behavior import (
    analyze_frame,
    aggregate_behavior_analysis,
)


logger = get_logger(
    "interview_routes"
)


router = APIRouter(
    prefix="/interview",
    tags=["Interview"]
)


class StartInterviewRequest(BaseModel):
    resume_id: str | None = None
    job_role: str = "General"
    interview_mode: str = "faang"


class CompleteInterviewRequest(BaseModel):
    overall_score: int | None = None
    behavior_summary: dict | None = None


interview_sessions = defaultdict(
    lambda: {
        "frames": [],
        "audio": [],
    }
)


def _record_vision_cost(
    interview_id: str,
    result: dict,
    latency_ms: int,
) -> dict | None:
    usage = result.pop("_usage", None)
    if not usage:
        return None

    tokens_in = int(usage.get("tokens_in") or 0)
    tokens_out = int(usage.get("tokens_out") or 0)
    model = usage.get("model") or "gemini-2.5-flash"
    cost_inr = estimate_gemini_cost_inr(
        model=model,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        input_modality="text_image_video",
    )

    return record_ai_cost(
        interview_id=interview_id,
        model=model,
        call_type="vision_frame",
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_inr=cost_inr,
        latency_ms=latency_ms,
    )


@router.post("/start")
async def start_interview(
    req: StartInterviewRequest,
    user: dict = Depends(get_current_user),
):

    interview_id = str(
        uuid.uuid4()
    )

    if req.interview_mode not in {"faang", "startup", "hr"}:
        raise HTTPException(status_code=400, detail="Invalid interview mode")

    if req.resume_id:
        resume = (
            supabase.table("resumes")
            .select("id")
            .eq("id", req.resume_id)
            .eq("user_id", user["sub"])
            .execute()
        )
        if not resume.data:
            raise HTTPException(status_code=404, detail="Resume not found")

    try:
        created = (
            supabase.table("interviews")
            .insert({
                "id": interview_id,
                "user_id": user["sub"],
                "resume_id": req.resume_id,
                "job_role": req.job_role.strip() or "General",
                "interview_mode": req.interview_mode,
                "status": "in_progress",
            })
            .execute()
        )
    except Exception as e:
        logger.exception(
            "interview_create_failed",
            user_id=user.get("sub"),
            error=str(e),
        )
        raise HTTPException(status_code=500, detail="Unable to create interview")

    interview_sessions[
        interview_id
    ] = {
        "frames": [],
        "audio": [],
    }

    return {
        "success": True,
        "interview_id": interview_id,
        "created_at": (
            created.data[0].get("created_at")
            if created.data
            else datetime.now(timezone.utc).isoformat()
        ),
    }


@router.get("/health")
async def health_check():

    return {
        "status": "ok",
        "service": "interview",
    }


@router.post("/analyze-frame")
async def analyze_webcam_frame(

    interview_id: str = Form(...),

    file: UploadFile = File(...),
):

    try:
        started_at = time.perf_counter()

        frame_bytes = await file.read()

        result = await analyze_frame(
            frame_bytes=frame_bytes,
            mime_type=file.content_type or "image/jpeg",
        )
        latency_ms = round((time.perf_counter() - started_at) * 1000)
        cost_record = _record_vision_cost(
            interview_id=interview_id,
            result=result,
            latency_ms=latency_ms,
        )

        interview_sessions[
            interview_id
        ]["frames"].append(result)

        return {
            "success": True,
            "analysis": result,
            "cost": cost_record,
            "session_cost": get_interview_cost_summary(interview_id),
        }

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

    duration_sec: float | None = Form(None),

    file: UploadFile = File(...),
):

    try:
        started_at = time.perf_counter()

        audio_bytes = await file.read()

        result = await transcribe_and_evaluate(
            audio_bytes=audio_bytes,
            question=question,
            mime_type=file.content_type or "audio/webm",
        )
        latency_ms = round((time.perf_counter() - started_at) * 1000)
        is_billable = bool(result.pop("_billable", False))
        cost_record = None

        if is_billable:
            cost_record = record_ai_cost(
                interview_id=interview_id,
                model=result.get("model") or settings.elevenlabs_stt_model,
                call_type="speech_to_text",
                cost_inr=estimate_elevenlabs_stt_cost_inr(duration_sec),
                latency_ms=latency_ms,
            )

        interview_sessions[
            interview_id
        ]["audio"].append(result)

        return {
            "success": True,
            "evaluation": result,
            "cost": cost_record,
            "session_cost": get_interview_cost_summary(interview_id),
        }

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
    interview_id: str
):

    try:

        frames = interview_sessions[
            interview_id
        ]["frames"]

        summary = (
            aggregate_behavior_analysis(
                frames
            )
        )

        return {
            "success": True,
            "summary": summary,
        }

    except Exception as e:

        logger.exception(
            "behavior_summary_failed",
            error=str(e),
        )

        return {
            "success": False,
            "error": str(e),
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

                frame_bytes = data["bytes"]

                result = await analyze_frame(
                    frame_bytes=frame_bytes,
                    mime_type="image/jpeg",
                )
                cost_record = _record_vision_cost(
                    interview_id=interview_id,
                    result=result,
                    latency_ms=0,
                )

                interview_sessions[
                    interview_id
                ]["frames"].append(result)

                await websocket.send_json({

                    "type": "vision",

                    "data": result,

                    "cost": cost_record,

                    "session_cost": get_interview_cost_summary(interview_id),
                })

            elif data.get("text") is not None:

                try:
                    payload = json.loads(
                        data["text"]
                    )
                except json.JSONDecodeError:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Invalid WebSocket JSON payload",
                    })
                    continue

                message_type = payload.get(
                    "type"
                )

                if message_type == "ping":

                    await websocket.send_json({
                        "type": "pong"
                    })

                elif message_type == "speak":

                    speech_text = str(payload.get("text") or "")
                    started_at = time.perf_counter()

                    speech = await synthesize_interviewer_speech(
                        text=speech_text,
                        voice_id=payload.get("voice_id"),
                    )
                    latency_ms = round((time.perf_counter() - started_at) * 1000)
                    speech["request_id"] = payload.get("request_id")
                    speech["text"] = speech_text

                    if speech.get("success"):
                        speech["cost"] = record_ai_cost(
                            interview_id=interview_id,
                            model=speech.get("model") or settings.elevenlabs_tts_model,
                            call_type="text_to_speech",
                            cost_inr=estimate_elevenlabs_tts_cost_inr(
                                model=speech.get("model") or settings.elevenlabs_tts_model,
                                text=speech_text,
                            ),
                            latency_ms=latency_ms,
                        )
                        speech["session_cost"] = get_interview_cost_summary(interview_id)

                    await websocket.send_json({

                        "type": "audio",

                        "data": speech,
                    })

                elif message_type == "summary":

                    summary = (
                        aggregate_behavior_analysis(
                            interview_sessions[
                                interview_id
                            ]["frames"]
                        )
                    )

                    await websocket.send_json({

                        "type": "summary",

                        "data": summary,

                        "session_cost": get_interview_cost_summary(interview_id),
                    })

                else:

                    await websocket.send_json({
                        "type": "error",
                        "message": f"Unsupported WebSocket message type: {message_type}",
                    })

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
    interview = (
        supabase.table("interviews")
        .select("id")
        .eq("id", interview_id)
        .eq("user_id", user["sub"])
        .execute()
    )

    if not interview.data:
        raise HTTPException(status_code=404, detail="Interview not found")

    summary = get_interview_cost_summary(interview_id)
    update_data = {
        "status": "completed",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "total_tokens": summary["total_tokens"],
    }

    if req.overall_score is not None:
        update_data["overall_score"] = max(0, min(100, req.overall_score))

    if req.behavior_summary is not None:
        update_data["behavior_notes"] = [req.behavior_summary]

    try:
        supabase.table("interviews").update(update_data).eq("id", interview_id).execute()
    except Exception as e:
        logger.exception(
            "interview_complete_failed",
            interview_id=interview_id,
            error=str(e),
        )
        raise HTTPException(status_code=500, detail="Unable to complete interview")

    return {
        "success": True,
        "interview_id": interview_id,
        "session_cost": summary,
    }
