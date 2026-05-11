import base64
import json
import asyncio
from statistics import mean

from google import genai

from backend.core.config import settings
from backend.core.logging import get_logger


logger = get_logger("behavior")


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
# Internal Sync Gemini Call
# =========================================================
def _generate_content(contents):

    return client.models.generate_content(
        model="gemini-2.5-flash",

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
    Analyze webcam frame for interview behavior.
    """

    try:

        # Encode image
        frame_b64 = base64.b64encode(
            frame_bytes
        ).decode("utf-8")

        response = await asyncio.to_thread(
            _generate_content,

            [
                {
                    "inline_data": {
                        "mime_type": mime_type,
                        "data": frame_b64,
                    }
                },

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
        )

        raw = response.text.strip()

        # Remove markdown wrappers
        if raw.startswith("```"):

            raw = (
                raw.replace("```json", "")
                .replace("```", "")
                .strip()
            )

        result = json.loads(raw)

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

    except json.JSONDecodeError:

        logger.warning(
            "behavior_parse_failed"
        )

        return DEFAULT_RESPONSE

    except Exception as e:

        logger.exception(
            "behavior_analysis_failed",
            error=str(e)
        )

        return {
            **DEFAULT_RESPONSE,
            "notes": str(e),
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
        ) / len(frames)
    )

    distraction_ratio = (
        sum(
            1 for f in frames
            if f.get("distracted")
        ) / len(frames)
    )

    emotions = [
        f.get("emotion", "neutral")
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