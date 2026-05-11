import base64
import json

from google import genai

from backend.core.config import settings
from backend.core.logging import get_logger


logger = get_logger("behavior")


# Gemini client
client = genai.Client(
    api_key=settings.google_api_key
)


async def analyze_frame(
    frame_bytes: bytes,
    mime_type: str = "image/jpeg"
) -> dict:
    """
    Analyze a single camera frame for candidate behavior.
    """

    try:

        # Convert image to base64
        frame_b64 = base64.b64encode(
            frame_bytes
        ).decode("utf-8")

        # Generate response
        response = client.models.generate_content(
            model="gemini-2.5-flash",

            contents=[
                {
                    "inline_data": {
                        "mime_type": mime_type,
                        "data": frame_b64
                    }
                },

                """
Analyze this image of a person during a job interview.

Return ONLY valid JSON:

{
    "engagement_score": 75,
    "eye_contact": true,
    "expression": "focused",
    "posture": "upright",
    "notes": "Brief observation"
}
"""
            ],

            config={
                "temperature": 0.2,
                "top_p": 0.8,
                "top_k": 40,
            }
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

        logger.info(
            "frame_analyzed",
            engagement=result.get(
                "engagement_score",
                0
            ),
            expression=result.get(
                "expression",
                "unknown"
            ),
        )

        return result

    # JSON Parsing Error
    except json.JSONDecodeError:

        logger.warning(
            "behavior_parse_failed"
        )

        return {
            "engagement_score": 50,
            "eye_contact": True,
            "expression": "neutral",
            "posture": "upright",
            "notes": "Could not parse Gemini response",
        }

    # General API Errors
    except Exception as e:

        logger.exception(
            "behavior_analysis_failed",
            error=str(e)
        )

        return {
            "engagement_score": 50,
            "eye_contact": True,
            "expression": "neutral",
            "posture": "upright",
            "notes": f"Behavior analysis failed: {str(e)}",
        }