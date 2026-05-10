async def analyze_frame(
    frame_bytes: bytes,
    mime_type: str = "image/jpeg"
) -> dict:
    """
    Analyze a single camera frame for candidate behavior.
    """

    frame_b64 = base64.b64encode(frame_bytes).decode()

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
        ]
    )

    raw = response.text.strip()

    if raw.startswith("```"):
        raw = raw.replace("```json", "").replace("```", "").strip()

    try:
        result = json.loads(raw)

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