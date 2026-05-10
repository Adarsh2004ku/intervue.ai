"""
Interview routes:
- POST /start — Initialize interview session, run Planner, return first question
- WebSocket /{id}/session — Real-time audio/video exchange
- GET /{id}/status — Get interview status
"""

import uuid
import json

from fastapi import (
    APIRouter,
    WebSocket,
    WebSocketDisconnect,
    HTTPException,
    Header,
)
from pydantic import BaseModel
from typing import Literal

from ai.graph.builder import build_interview_graph
from ai.personas.interviewer_personas import get_persona

from backend.services.audio.gemini_stt import (
    transcribe_and_evaluate_with_retry,
)
from backend.services.vision.behavior import analyze_frame

from backend.db.session import supabase, redis_client
from backend.core.config import settings
from backend.core.security import decode_access_token
from backend.core.logging import get_logger


logger = get_logger("interview_routes")

router = APIRouter()


class StartInterviewRequest(BaseModel):
    resume_id: str
    job_role: str
    interview_mode: Literal["faang", "startup", "hr"] = "faang"


class StartInterviewResponse(BaseModel):
    interview_id: str
    first_question: dict
    persona_name: str
    opening_line: str


@router.post("/start", response_model=StartInterviewResponse)
async def start_interview(
    req: StartInterviewRequest,
    authorization: str = Header(default=""),
):
    """
    Start a new interview session.
    """

    # Validate JWT
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid token",
        )

    token = authorization.replace("Bearer ", "").strip()

    payload = decode_access_token(token)

    if not payload:
        raise HTTPException(
            status_code=401,
            detail="Invalid token",
        )

    user_id = payload["sub"]

    # Verify resume exists
    resume_result = (
        supabase
        .table("resumes")
        .select("*")
        .eq("id", req.resume_id)
        .execute()
    )

    if not resume_result.data:
        raise HTTPException(
            status_code=404,
            detail="Resume not found",
        )

    resume = resume_result.data[0]

    persona = get_persona(req.interview_mode)

    # Create interview record
    interview_id = str(uuid.uuid4())

    # Initial LangGraph state
    initial_state = {
        "user_id": user_id,
        "resume_id": req.resume_id,
        "job_role": req.job_role,
        "interview_mode": req.interview_mode,
        "resume_summary": resume.get("parsed_json", {}),
        "questions": [],
        "answers": [],
        "evaluations": [],
        "behavior_data": [],
        "current_index": 0,
    }

    # Run interview graph
    graph = build_interview_graph()

    result = graph.invoke(initial_state)

    # First question fallback
    first_question = (
        result["questions"][0]
        if result.get("questions")
        else {
            "text": persona["opening_line"],
            "category": "General",
            "topic": req.job_role,
            "difficulty": "medium",
            "why_asked": "Opening question",
            "is_weakness_focused": False,
            "order_idx": 0,
        }
    )

    # Store interview
    (
        supabase
        .table("interviews")
        .insert({
            "id": interview_id,
            "user_id": user_id,
            "resume_id": req.resume_id,
            "job_role": req.job_role,
            "interview_mode": req.interview_mode,
            "status": "in_progress",
            "langgraph_thread_id": str(uuid.uuid4()),
        })
        .execute()
    )

    # Store first question
    (
        supabase
        .table("questions")
        .insert({
            "id": str(uuid.uuid4()),
            "interview_id": interview_id,
            "text": first_question.get("text", ""),
            "category": first_question.get("category", ""),
            "topic": first_question.get("topic", ""),
            "difficulty": first_question.get("difficulty", ""),
            "why_asked": first_question.get("why_asked", ""),
            "is_weakness_focused": first_question.get(
                "is_weakness_focused",
                False,
            ),
            "order_idx": 0,
        })
        .execute()
    )

    # Save interview state to Redis
    redis_client.setex(
        f"interview_state:{interview_id}",
        7200,
        json.dumps(result),
    )

    logger.info(
        "interview_started",
        interview_id=interview_id,
        mode=req.interview_mode,
        user_id=user_id,
    )

    return StartInterviewResponse(
        interview_id=interview_id,
        first_question=first_question,
        persona_name=persona["name"],
        opening_line=persona["opening_line"],
    )


@router.websocket("/{interview_id}/session")
async def interview_session(
    websocket: WebSocket,
    interview_id: str,
):
    """
    Real-time interview session.
    """

    await websocket.accept()

    logger.info(
        "websocket_connected",
        interview_id=interview_id,
    )

    # Load state from Redis
    state_json = redis_client.get(
        f"interview_state:{interview_id}"
    )

    if not state_json:
        await websocket.send_json({
            "type": "error",
            "message": "Interview session not found",
        })

        await websocket.close()

        return

    interview_state = json.loads(state_json)

    try:

        while True:

            data = await websocket.receive()

            # Binary data (audio/frame)
            if "bytes" in data:

                binary_data = data["bytes"]

                current_question = (
                    interview_state["questions"][-1]
                    if interview_state.get("questions")
                    else {}
                )

                # AUDIO
                result = await transcribe_and_evaluate_with_retry(
                    audio_bytes=binary_data,
                    question=current_question.get("text", ""),
                )

                interview_state["answers"].append({
                    "transcript": result["transcript"],
                })

                interview_state["evaluations"].append({
                    "score": result["score"],
                    "accuracy_score": result["accuracy_score"],
                    "clarity_score": result["clarity_score"],
                    "depth_score": result["depth_score"],
                    "cot_reasoning": result["cot_reasoning"],
                })

                interview_state["current_index"] += 1

                # Interview complete
                if (
                    interview_state["current_index"]
                    >= settings.max_questions_per_interview
                ):

                    from ai.agents.coach import coach_agent

                    interview_state = {
                        **interview_state,
                        **coach_agent(interview_state),
                    }

                    await websocket.send_json({
                        "type": "interview_complete",
                        "overall_score": interview_state["report"].get(
                            "overall_score",
                            0,
                        ),
                        "grade": interview_state["report"].get(
                            "grade",
                            "",
                        ),
                        "report": interview_state["report"],
                    })

                    _save_interview_to_db(
                        interview_id,
                        interview_state,
                    )

                    break

                # Generate next question
                from ai.agents.retriever import retriever_agent
                from ai.agents.generator import generator_agent

                interview_state = {
                    **interview_state,
                    **retriever_agent(interview_state),
                }

                interview_state = {
                    **interview_state,
                    **generator_agent(interview_state),
                }

                next_question = (
                    interview_state["questions"][-1]
                )

                # Store question
                (
                    supabase
                    .table("questions")
                    .insert({
                        "id": str(uuid.uuid4()),
                        "interview_id": interview_id,
                        "text": next_question.get("text", ""),
                        "category": next_question.get("category", ""),
                        "topic": next_question.get("topic", ""),
                        "difficulty": next_question.get(
                            "difficulty",
                            "",
                        ),
                        "why_asked": next_question.get(
                            "why_asked",
                            "",
                        ),
                        "is_weakness_focused": next_question.get(
                            "is_weakness_focused",
                            False,
                        ),
                        "order_idx": interview_state["current_index"],
                    })
                    .execute()
                )

                # Send response
                await websocket.send_json({
                    "type": "next_question",
                    "question": next_question.get("text", ""),
                    "question_number": (
                        interview_state["current_index"] + 1
                    ),
                    "topic": next_question.get("topic", ""),
                    "why_asked": next_question.get(
                        "why_asked",
                        "",
                    ),
                    "previous_score": result["score"],
                    "previous_reasoning": result[
                        "cot_reasoning"
                    ],
                })

            # Text control messages
            elif "text" in data:

                msg = json.loads(data["text"])

                if msg.get("type") == "ping":

                    await websocket.send_json({
                        "type": "pong",
                    })

            # Persist state
            redis_client.setex(
                f"interview_state:{interview_id}",
                7200,
                json.dumps(interview_state),
            )

    except WebSocketDisconnect:

        logger.info(
            "websocket_disconnected",
            interview_id=interview_id,
        )

        _save_interview_to_db(
            interview_id,
            interview_state,
            status="aborted",
        )

    except Exception as e:

        logger.error(
            "websocket_error",
            interview_id=interview_id,
            error=str(e),
        )

        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e),
            })
        except Exception:
            pass


def _save_interview_to_db(
    interview_id: str,
    state: dict,
    status: str = "completed",
):
    """
    Save final interview state.
    """

    report = state.get("report", {})

    # Update interview
    (
        supabase
        .table("interviews")
        .update({
            "status": status,
            "overall_score": report.get(
                "overall_score"
            ),
            "completed_at": "now()",
        })
        .eq("id", interview_id)
        .execute()
    )

    # Save answers
    for i, (q, a, e) in enumerate(
        zip(
            state.get("questions", []),
            state.get("answers", []),
            state.get("evaluations", []),
        )
    ):

        q_result = (
            supabase
            .table("questions")
            .select("id")
            .eq("interview_id", interview_id)
            .eq("order_idx", i)
            .execute()
        )

        if q_result.data:

            (
                supabase
                .table("answers")
                .upsert({
                    "question_id": q_result.data[0]["id"],
                    "answer_text": a.get("transcript", ""),
                    "score": e.get("score", 0),
                    "accuracy_score": e.get(
                        "accuracy_score",
                        0,
                    ),
                    "clarity_score": e.get(
                        "clarity_score",
                        0,
                    ),
                    "depth_score": e.get(
                        "depth_score",
                        0,
                    ),
                    "cot_reasoning": e.get(
                        "cot_reasoning",
                        "",
                    ),
                })
                .execute()
            )

    # Save report
    (
        supabase
        .table("reports")
        .upsert({
            "interview_id": interview_id,
            "overall_score": report.get(
                "overall_score",
                0,
            ),
            "grade": report.get("grade", ""),
            "interview_readiness": report.get(
                "interview_readiness",
                "not_ready",
            ),
            "feedback_json": report.get(
                "per_topic_feedback",
                {},
            ),
            "improvement_plan": report.get(
                "improvement_plan",
                [],
            ),
            "speech_summary": report.get(
                "speech_summary",
                {},
            ),
            "strengths": report.get(
                "strengths_to_highlight",
                [],
            ),
            "next_session_focus": report.get(
                "next_session_focus",
                [],
            ),
        })
        .execute()
    )

    logger.info(
        "interview_saved_to_db",
        interview_id=interview_id,
        status=status,
    )