import json

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from pydantic import BaseModel

from backend.core.logging import get_logger
from backend.core.security import decode_access_token, get_current_user
from backend.services.interview_agent_flow import (
    analyze_interview_frame,
    complete_interview_session,
    create_interview_session,
    evaluate_audio_answer,
    get_behavior_summary_payload,
    get_interview_status_payload,
    list_interviews_for_user,
    synthesize_question_audio,
    verify_interview_access,
)


logger = get_logger("interview_routes")


router = APIRouter(prefix="/interview", tags=["Interview"])


class StartInterviewRequest(BaseModel):
    resume_id: str | None = None
    job_role: str = "General"
    job_description: str = ""
    interview_mode: str = "faang"


class CompleteInterviewRequest(BaseModel):
    overall_score: int | None = None
    behavior_summary: dict | None = None


async def _authenticate_websocket(
    websocket: WebSocket,
    interview_id: str,
) -> dict | None:
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return None

    try:
        user = decode_access_token(token)
        verify_interview_access(interview_id=interview_id, user_id=user["sub"])
        return user
    except Exception as e:
        logger.warning(
            "websocket_auth_failed",
            interview_id=interview_id,
            error=str(e),
        )
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return None


@router.post("/start")
async def start_interview(
    req: StartInterviewRequest,
    user: dict = Depends(get_current_user),
):
    try:
        return create_interview_session(
            user_id=user["sub"],
            resume_id=req.resume_id,
            job_role=req.job_role,
            job_description=req.job_description,
            interview_mode=req.interview_mode,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(
            "interview_create_failed",
            user_id=user.get("sub"),
            error=str(e),
        )
        raise HTTPException(status_code=500, detail="Unable to create interview")


@router.get("/history")
async def list_interview_history(user: dict = Depends(get_current_user)):
    """List interviews stored in the database for the current user."""
    return {"interviews": list_interviews_for_user(user["sub"])}


@router.get("/{interview_id}/status")
async def get_interview_status(
    interview_id: str,
    user: dict = Depends(get_current_user),
):
    """Return an interview row with persisted questions for resume/reload flows."""
    payload = get_interview_status_payload(
        interview_id=interview_id,
        user_id=user["sub"],
    )
    if not payload:
        raise HTTPException(status_code=404, detail="Interview not found")
    return payload


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
    user: dict = Depends(get_current_user),
):
    try:
        frame_bytes = await file.read()
        return await analyze_interview_frame(
            interview_id=interview_id,
            user_id=user["sub"],
            frame_bytes=frame_bytes,
            mime_type=file.content_type or "image/jpeg",
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
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
    user: dict = Depends(get_current_user),
):
    try:
        audio_bytes = await file.read()
        return await evaluate_audio_answer(
            interview_id=interview_id,
            user_id=user["sub"],
            question=question,
            audio_bytes=audio_bytes,
            mime_type=file.content_type or "audio/webm",
            duration_sec=duration_sec,
        )

    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
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
        return get_behavior_summary_payload(
            interview_id=interview_id,
            user_id=user["sub"],
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
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
    user = await _authenticate_websocket(websocket, interview_id)
    if not user:
        return

    await websocket.accept()

    logger.info(
        "websocket_connected",
        interview_id=interview_id,
    )

    try:
        while True:
            try:
                data = await websocket.receive()
            except RuntimeError as e:
                if "disconnect message has been received" in str(e):
                    logger.info(
                        "websocket_disconnected",
                        interview_id=interview_id,
                    )
                    break
                raise

            if data.get("type") == "websocket.disconnect":
                logger.info(
                    "websocket_disconnected",
                    interview_id=interview_id,
                    code=data.get("code"),
                    reason=data.get("reason"),
                )
                break

            if data.get("bytes") is not None:
                frame_bytes = data["bytes"]
                frame_result = await analyze_interview_frame(
                    interview_id=interview_id,
                    user_id=user["sub"],
                    frame_bytes=frame_bytes,
                    mime_type="image/jpeg",
                )

                await websocket.send_json(
                    {
                        "type": "vision",
                        "data": frame_result.get("analysis"),
                        "cost": frame_result.get("cost"),
                        "session_cost": frame_result.get("session_cost"),
                    }
                )

            elif data.get("text") is not None:
                try:
                    payload = json.loads(data["text"])
                except json.JSONDecodeError:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Invalid WebSocket JSON payload",
                    })
                    continue

                message_type = payload.get("type")

                if message_type == "ping":
                    await websocket.send_json({
                        "type": "pong"
                    })

                elif message_type == "speak":
                    speech_text = str(payload.get("text") or "")
                    speech = await synthesize_question_audio(
                        interview_id=interview_id,
                        user_id=user["sub"],
                        text=speech_text,
                        voice_id=payload.get("voice_id"),
                        request_id=payload.get("request_id"),
                    )

                    await websocket.send_json(
                        {
                            "type": "audio",
                            "data": speech,
                        }
                    )

                elif message_type == "summary":
                    summary_payload = get_behavior_summary_payload(
                        interview_id=interview_id,
                        user_id=user["sub"],
                    )

                    await websocket.send_json(
                        {
                            "type": "summary",
                            "data": summary_payload["summary"],
                            "session_cost": summary_payload["session_cost"],
                        }
                    )

                else:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Unsupported WebSocket message type: {message_type}",
                    })

    except (LookupError, WebSocketDisconnect):
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
        completed = complete_interview_session(
            interview_id=interview_id,
            user_id=user["sub"],
            overall_score=req.overall_score,
            behavior_summary=req.behavior_summary,
        )
    except Exception as e:
        logger.exception(
            "interview_complete_failed",
            interview_id=interview_id,
            error=str(e),
        )
        raise HTTPException(status_code=500, detail="Unable to complete interview")

    if not completed:
        raise HTTPException(status_code=404, detail="Interview not found")

    return completed
