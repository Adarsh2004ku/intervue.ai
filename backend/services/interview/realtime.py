import json
import time

from fastapi import WebSocket

from backend.core.config import settings
from backend.services.audio.elevenlabs_tts import synthesize_interviewer_speech
from backend.services.cost_tracking import (
    estimate_elevenlabs_tts_cost_inr,
    get_interview_cost_summary,
    record_vision_cost,
    record_ai_cost,
)
from backend.services.interview.session_state import append_session_item, get_session_frames
from backend.services.vision.behavior import aggregate_behavior_analysis, analyze_frame


async def handle_websocket_frame(
    websocket: WebSocket,
    interview_id: str,
    frame_bytes: bytes,
) -> None:
    result = await analyze_frame(
        frame_bytes=frame_bytes,
        mime_type="image/jpeg",
    )
    cost_record = record_vision_cost(
        interview_id=interview_id,
        result=result,
        latency_ms=0,
    )
    if not result.get("analysis_unavailable"):
        append_session_item(interview_id, "frames", result)

    await websocket.send_json({
        "type": "vision",
        "data": result,
        "cost": cost_record,
        "session_cost": get_interview_cost_summary(interview_id),
    })


async def handle_websocket_text(
    websocket: WebSocket,
    interview_id: str,
    text: str,
) -> None:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        await websocket.send_json({
            "type": "error",
            "message": "Invalid WebSocket JSON payload",
        })
        return

    message_type = payload.get("type")

    if message_type == "ping":
        await websocket.send_json({"type": "pong"})
    elif message_type == "speak":
        await _handle_websocket_speak(websocket, interview_id, payload)
    elif message_type == "summary":
        await websocket.send_json({
            "type": "summary",
            "data": aggregate_behavior_analysis(get_session_frames(interview_id)),
            "session_cost": get_interview_cost_summary(interview_id),
        })
    else:
        await websocket.send_json({
            "type": "error",
            "message": f"Unsupported WebSocket message type: {message_type}",
        })


async def _handle_websocket_speak(
    websocket: WebSocket,
    interview_id: str,
    payload: dict,
) -> None:
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
