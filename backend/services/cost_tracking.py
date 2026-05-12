from __future__ import annotations

from collections import defaultdict
from typing import Any

from backend.core.config import settings
from backend.core.logging import get_logger
from backend.db.session import supabase


logger = get_logger("cost_tracking")

GEMINI_FLASH_INPUT_USD_PER_1M = 0.30
GEMINI_FLASH_AUDIO_INPUT_USD_PER_1M = 1.00
GEMINI_FLASH_OUTPUT_USD_PER_1M = 2.50
GEMINI_FLASH_LITE_INPUT_USD_PER_1M = 0.10
GEMINI_FLASH_LITE_AUDIO_INPUT_USD_PER_1M = 0.30
GEMINI_FLASH_LITE_OUTPUT_USD_PER_1M = 0.40

ELEVENLABS_SCRIBE_USD_PER_HOUR = 0.22
ELEVENLABS_FLASH_TTS_USD_PER_1K_CHARS = 0.05
ELEVENLABS_MULTILINGUAL_TTS_USD_PER_1K_CHARS = 0.10


def _as_int(value: Any) -> int:
    if isinstance(value, (int, float)):
        return max(0, int(value))
    return 0


def _attr(source: Any, *names: str) -> Any:
    for name in names:
        if isinstance(source, dict) and name in source:
            return source[name]
        value = getattr(source, name, None)
        if value is not None:
            return value
    return None


def _round_inr(value: float) -> float:
    return round(max(0.0, value), 6)


def usd_to_inr(usd: float) -> float:
    return _round_inr(usd * settings.api_cost_usd_to_inr)


def extract_gemini_usage(response: Any) -> dict[str, int]:
    usage = _attr(response, "usage_metadata", "usageMetadata")
    if usage is None:
        return {"tokens_in": 0, "tokens_out": 0}

    tokens_in = _as_int(
        _attr(usage, "prompt_token_count", "promptTokenCount", "input_tokens")
    )
    tokens_out = _as_int(
        _attr(
            usage,
            "candidates_token_count",
            "candidatesTokenCount",
            "output_tokens",
        )
    )
    total_tokens = _as_int(
        _attr(usage, "total_token_count", "totalTokenCount", "total_tokens")
    )

    if not tokens_out and total_tokens > tokens_in:
        tokens_out = total_tokens - tokens_in

    return {
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
    }


def estimate_gemini_cost_inr(
    model: str,
    tokens_in: int,
    tokens_out: int,
    input_modality: str = "text_image_video",
) -> float:
    model_name = model.lower()
    is_audio = input_modality == "audio"

    if "flash-lite" in model_name:
        input_rate = (
            GEMINI_FLASH_LITE_AUDIO_INPUT_USD_PER_1M
            if is_audio
            else GEMINI_FLASH_LITE_INPUT_USD_PER_1M
        )
        output_rate = GEMINI_FLASH_LITE_OUTPUT_USD_PER_1M
    else:
        input_rate = (
            GEMINI_FLASH_AUDIO_INPUT_USD_PER_1M
            if is_audio
            else GEMINI_FLASH_INPUT_USD_PER_1M
        )
        output_rate = GEMINI_FLASH_OUTPUT_USD_PER_1M

    usd = ((tokens_in / 1_000_000) * input_rate) + (
        (tokens_out / 1_000_000) * output_rate
    )
    return usd_to_inr(usd)


def estimate_elevenlabs_stt_cost_inr(duration_sec: float | None) -> float:
    if not duration_sec:
        return 0.0
    return usd_to_inr((max(0.0, duration_sec) / 3600) * ELEVENLABS_SCRIBE_USD_PER_HOUR)


def estimate_elevenlabs_tts_cost_inr(model: str, text: str) -> float:
    model_name = model.lower()
    rate = (
        ELEVENLABS_MULTILINGUAL_TTS_USD_PER_1K_CHARS
        if "multilingual" in model_name
        else ELEVENLABS_FLASH_TTS_USD_PER_1K_CHARS
    )
    return usd_to_inr((len(text.strip()) / 1000) * rate)


def record_ai_cost(
    *,
    interview_id: str | None,
    model: str,
    call_type: str,
    tokens_in: int = 0,
    tokens_out: int = 0,
    cost_inr: float = 0.0,
    latency_ms: int | None = None,
) -> dict[str, Any] | None:
    payload = {
        "interview_id": interview_id,
        "model": model,
        "call_type": call_type,
        "tokens_in": _as_int(tokens_in),
        "tokens_out": _as_int(tokens_out),
        "cost_inr": _round_inr(cost_inr),
        "latency_ms": latency_ms,
    }

    try:
        result = supabase.table("ai_costs").insert(payload).execute()
        row = result.data[0] if result.data else payload
        logger.info(
            "ai_cost_recorded",
            interview_id=interview_id,
            model=model,
            call_type=call_type,
            cost_inr=payload["cost_inr"],
        )
        return row
    except Exception as e:
        logger.exception(
            "ai_cost_record_failed",
            interview_id=interview_id,
            model=model,
            call_type=call_type,
            error=str(e),
        )
        return None


def get_interview_cost_summary(interview_id: str) -> dict[str, Any]:
    try:
        result = (
            supabase.table("ai_costs")
            .select("model, call_type, cost_inr, tokens_in, tokens_out, latency_ms, created_at")
            .eq("interview_id", interview_id)
            .execute()
        )
        records = result.data or []
    except Exception as e:
        logger.exception(
            "interview_cost_summary_failed",
            interview_id=interview_id,
            error=str(e),
        )
        records = []

    by_call_type: dict[str, float] = defaultdict(float)
    total_tokens = 0
    total_cost = 0.0

    for record in records:
        cost = float(record.get("cost_inr") or 0)
        call_type = record.get("call_type") or "unknown"
        by_call_type[call_type] += cost
        total_cost += cost
        total_tokens += int(record.get("tokens_in") or 0) + int(record.get("tokens_out") or 0)

    return {
        "interview_id": interview_id,
        "total_cost_inr": round(total_cost, 4),
        "total_tokens": total_tokens,
        "calls": len(records),
        "by_call_type": {
            key: round(value, 4)
            for key, value in sorted(by_call_type.items())
        },
        "records": records,
    }
