import base64,json
import google.generativeai as genai
from backend.core.config import settings
from backend.core.logging import get_logger

logger = get_logger("behavior")

genai.configure(api_key = settings.google_api_key)

async def analyze_frame(frame_bytes : bytes,
                        mime_type : str = "image/jpeg")->dict:
    """
    Analyze a single camera frame for candidate behavior.
    Returns: engagement_score (0-100), eye_contact (bool),
    expression (str), notes (str)
    """
    model = genai.GenerativeModel("gemini-2.5-flash")
    frame_b64 = base64.b64encode(frame_bytes).decode()
    

    response = model.generate_content(
        [
            {"inline_data": {"mime_type": mime_type, "data": frame_b64}},
            """Analyze this image of a person during a job interview.
        Return ONLY valid JSON:
        {
            "engagement_score": 75,
            "eye_contact": true,
            "expression": "focused",
            "posture": "upright",
            "notes": "Brief observation about the candidate's demeanor"
        }

        engagement_score: 0-100 rating of how engaged the person appears
        eye_contact: whether the person appears to be looking at the camera/screen
        expression: one of [neutral, focused, confused, confident, nervous, smiling, distracted]
        posture: one of [upright, leaning_forward, leaning_back, slouched]""",
                ]
            )
    
    raw = response.text.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        if len(parts) >= 2:
            raw = parts[1]
        if raw.startswith("json"):
            raw = raw[4:]

    try:
        result = json.loads(raw.strip())
        logger.info(
            "frame_analyzed",
            engagement=result.get("engagement_score", 0),
            expression=result.get("expression", "unknown"),
        )
        return result
    except json.JSONDecodeError:
        logger.warning("behavior_parse_failed")
        return {
            "engagement_score": 50,
            "eye_contact": True,
            "expression": "neutral",
            "posture": "upright",
            "notes": "Could not analyze frame",
        }