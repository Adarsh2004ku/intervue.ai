import asyncio
import json
import re
from statistics import mean

from google import genai
from google.genai import types

from backend.core.config import settings
from backend.core.logging import get_logger
from backend.services.cost_tracking import extract_gemini_usage


logger = get_logger("behavior")
GEMINI_VISION_MODEL = "gemini-2.5-flash"


# =========================================================
# Gemini Client
# =========================================================
client = genai.Client(
    api_key=settings.google_api_key
)


# =========================================================
# Default Response
# =========================================================
DEFAULT_RESPONSE = {
    "engagement_score": 50,
    "confidence_score": 50,
    "nervousness_score": 50,
    "professionalism_score": 50,
    "eye_contact": True,
    "looking_away": False,
    "distracted": False,
    "expression": "neutral",
    "emotion": "neutral",
    "posture": "upright",
    "confidence_level": "medium",
    "notes": "Could not analyze behavior",
}


# =========================================================
# Internal Sync Function
# =========================================================
def _generate_content(contents):

    return client.models.generate_content(
        model=GEMINI_VISION_MODEL,

        contents=contents,

        config={
            "temperature": 0.2,
            "top_p": 0.8,
            "top_k": 40,
        }
    )


# =========================================================
# Analyze Single Frame
# =========================================================
async def analyze_frame(
    frame_bytes: bytes,
    mime_type: str = "image/jpeg"
) -> dict:
    """
    Analyze a single camera frame
    for interview behavior.
    """

    try:

        # =================================================
        # Empty Frame Protection
        # =================================================
        if not frame_bytes:
            raise ValueError(
                "Empty frame received"
            )

        # =================================================
        # Gemini Vision Request
        # =================================================
        response = await asyncio.wait_for(

            asyncio.to_thread(

                _generate_content,

                [
                    types.Part.from_bytes(
                        data=frame_bytes,
                        mime_type=mime_type,
                    ),

                    """
Analyze this image of a candidate during a professional job interview.

Evaluate:

- engagement
- confidence
- nervousness
- professionalism
- eye contact
- posture
- facial expression
- distraction level

Return ONLY valid JSON.

Example:

{
    "engagement_score": 82,
    "confidence_score": 76,
    "nervousness_score": 25,
    "professionalism_score": 88,
    "eye_contact": true,
    "looking_away": false,
    "distracted": false,
    "expression": "focused",
    "emotion": "confident",
    "posture": "upright",
    "confidence_level": "high",
    "notes": "Candidate appears attentive and confident"
}

Rules:
- scores must be between 0 and 100
- no markdown
- no explanation
- return only JSON
"""
                ]
            ),

            timeout=20
        )

        # =================================================
        # Safe Response Extraction
        # =================================================
        raw = (
            response.text.strip()
            if response.text
            else "{}"
        )

        logger.info(
            "vision_raw_response",
            raw=raw
        )

        # =================================================
        # Remove Markdown Wrappers
        # =================================================
        if raw.startswith("```"):

            raw = (
                raw.replace("```json", "")
                .replace("```", "")
                .strip()
            )

        # =================================================
        # Safe JSON Extraction
        # =================================================
        match = re.search(
            r'\{[\s\S]*\}',
            raw
        )

        if not match:

            raise ValueError(
                "No valid JSON found"
            )

        result = json.loads(
            match.group()
        )

        # =================================================
        # Validate Response
        # =================================================
        validated = {

            "engagement_score": int(
                result.get(
                    "engagement_score",
                    50
                )
            ),

            "confidence_score": int(
                result.get(
                    "confidence_score",
                    50
                )
            ),

            "nervousness_score": int(
                result.get(
                    "nervousness_score",
                    50
                )
            ),

            "professionalism_score": int(
                result.get(
                    "professionalism_score",
                    50
                )
            ),

            "eye_contact": bool(
                result.get(
                    "eye_contact",
                    True
                )
            ),

            "looking_away": bool(
                result.get(
                    "looking_away",
                    False
                )
            ),

            "distracted": bool(
                result.get(
                    "distracted",
                    False
                )
            ),

            "expression": str(
                result.get(
                    "expression",
                    "neutral"
                )
            ),

            "emotion": str(
                result.get(
                    "emotion",
                    "neutral"
                )
            ),

            "posture": str(
                result.get(
                    "posture",
                    "upright"
                )
            ),

            "confidence_level": str(
                result.get(
                    "confidence_level",
                    "medium"
                )
            ),

            "notes": str(
                result.get(
                    "notes",
                    ""
                )
            ),
        }

        validated["_usage"] = {
            "model": GEMINI_VISION_MODEL,
            **extract_gemini_usage(response),
        }

        logger.info(

            "frame_analyzed",

            engagement=validated[
                "engagement_score"
            ],

            confidence=validated[
                "confidence_score"
            ],

            emotion=validated[
                "emotion"
            ],
        )

        return validated

    # =====================================================
    # JSON Parse Error
    # =====================================================
    except json.JSONDecodeError as e:

        logger.warning(

            "behavior_parse_failed",

            error=str(e),
        )

        return {
            **DEFAULT_RESPONSE,
            "notes": (
                "Could not parse Gemini response"
            ),
        }

    # =====================================================
    # Timeout Error
    # =====================================================
    except asyncio.TimeoutError:

        logger.error(
            "vision_timeout"
        )

        return {
            **DEFAULT_RESPONSE,
            "notes": "Gemini request timeout",
        }

    # =====================================================
    # General Errors
    # =====================================================
    except Exception as e:

        logger.exception(

            "behavior_analysis_failed",

            error=str(e)
        )

        return {
            **DEFAULT_RESPONSE,
            "notes": (
                f"Behavior analysis failed: {str(e)}"
            ),
        }


# =========================================================
# Aggregate Interview Behavior
# =========================================================
def aggregate_behavior_analysis(
    frames: list[dict]
) -> dict:
    """
    Aggregate multiple frame analyses
    into final interview behavior analytics.
    """

    if not frames:

        return {

            "overall_engagement": 0,

            "overall_confidence": 0,

            "overall_professionalism": 0,

            "overall_nervousness": 0,

            "eye_contact_ratio": 0,

            "distraction_ratio": 0,

            "dominant_emotion": "neutral",

            "behavior_summary": (
                "No behavior data available"
            ),
        }

    eye_contact_ratio = (

        sum(
            1 for f in frames
            if f.get("eye_contact")
        )

        / len(frames)
    )

    distraction_ratio = (

        sum(
            1 for f in frames
            if f.get("distracted")
        )

        / len(frames)
    )

    emotions = [

        f.get(
            "emotion",
            "neutral"
        )

        for f in frames
    ]

    dominant_emotion = max(
        set(emotions),
        key=emotions.count
    )

    return {

        "overall_engagement": round(

            mean(
                f.get(
                    "engagement_score",
                    50
                )

                for f in frames
            ),

            2,
        ),

        "overall_confidence": round(

            mean(
                f.get(
                    "confidence_score",
                    50
                )

                for f in frames
            ),

            2,
        ),

        "overall_professionalism": round(

            mean(
                f.get(
                    "professionalism_score",
                    50
                )

                for f in frames
            ),

            2,
        ),

        "overall_nervousness": round(

            mean(
                f.get(
                    "nervousness_score",
                    50
                )

                for f in frames
            ),

            2,
        ),

        "eye_contact_ratio": round(
            eye_contact_ratio * 100,
            2,
        ),

        "distraction_ratio": round(
            distraction_ratio * 100,
            2,
        ),

        "dominant_emotion": dominant_emotion,

        "behavior_summary": (

            f"Candidate showed "

            f"{dominant_emotion} behavior "

            f"with "

            f"{round(eye_contact_ratio * 100)}% "

            f"eye contact consistency."
        ),
    }
