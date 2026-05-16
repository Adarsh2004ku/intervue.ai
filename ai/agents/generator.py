import asyncio
import hashlib
import json
import random
import re
from collections import Counter
from typing import Any

from ai.agents.llm import invoke_llm_text
from ai.agents.state import InterviewState
from ai.personas.interviewer_personas import get_persona
from backend.core.config import settings
from backend.core.logging import get_logger


logger = get_logger("generator_agent")


QUESTION_BANK = {
    "faang": [
        "Walk me through one technically challenging project from your resume. What trade-offs did you make, and how did you validate the result?",
        "Describe a difficult bug or performance issue you solved. How did you isolate the root cause?",
        "Pick a system you have built. How would you scale it if usage increased by 10x?",
        "Tell me about an edge case you almost missed and how you handled it.",
    ],
    "startup": [
        "Tell me about a product or feature you shipped under constraints. What did you prioritize, and what would you improve now?",
        "Tell me about a time you had to move fast with incomplete information. What did you do?",
        "What is one product decision you influenced, and how did you measure whether it worked?",
        "Describe a moment when you took ownership beyond your assigned role.",
    ],
    "hr": [
        "Tell me about yourself and a recent experience that shows how you work with a team.",
        "Tell me about a time you handled conflict with a teammate or stakeholder.",
        "Describe a failure or setback. What did you learn, and what changed afterward?",
        "What kind of work environment helps you do your best work?",
    ],
}

CONTEXT_STOP_WORDS = {
    "about",
    "across",
    "also",
    "and",
    "are",
    "based",
    "build",
    "candidate",
    "company",
    "design",
    "develop",
    "experience",
    "for",
    "from",
    "have",
    "into",
    "job",
    "looking",
    "must",
    "our",
    "role",
    "should",
    "skills",
    "team",
    "that",
    "the",
    "their",
    "this",
    "using",
    "with",
    "work",
    "you",
    "your",
}


def clean_job_description(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()[:6000]


def job_description_terms(job_description: str) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9+#.-]{2,}", job_description.lower())
    useful_words = [
        word.strip(".-")
        for word in words
        if word not in CONTEXT_STOP_WORDS and len(word.strip(".-")) >= 3
    ]
    return [word for word, _ in Counter(useful_words).most_common(4)]


def _human_join(items: list[str]) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return f"{', '.join(items[:-1])}, and {items[-1]}"


def _context_questions(
    job_role: str,
    job_description: str,
    resume_context: str,
) -> list[str]:
    focus = _human_join(job_description_terms(f"{job_description} {resume_context}"))
    if not focus:
        return []

    role = job_role or "this role"
    context_label = (
        "resume and job description"
        if job_description and resume_context
        else "job description"
        if job_description
        else "resume"
    )
    return [
        (
            f"This {role} role emphasizes {focus}. Which experience from your "
            f"{context_label} best proves you can handle that, and what evidence "
            "would you point to?"
        ),
        (
            f"Describe a project where you used {focus} in a real delivery "
            "context. What trade-offs did you make?"
        ),
        (
            f"If you joined as a {role}, what would you prioritize in your "
            f"first 30 days based on the {context_label}?"
        ),
        (
            f"Which requirement around {focus} would be your biggest stretch, "
            "and how would you close the gap?"
        ),
        (
            f"Imagine the team asks you to improve a system involving {focus}. "
            "What would you inspect first, and how would you decide whether your change worked?"
        ),
        (
            f"Tell me about a time you had to learn or apply {focus} quickly. "
            "What made the learning stick?"
        ),
        (
            f"How would you explain your strongest {focus} experience to a "
            "non-technical stakeholder?"
        ),
        (
            f"What risks would you watch for in a {role} role that depends on "
            f"{focus}, and how would you reduce them?"
        ),
        (
            f"Give me an example of a decision you made where {focus} affected "
            "the implementation approach."
        ),
        (
            f"Which part of this {role} opportunity around {focus} would you "
            "want to clarify with the hiring manager?"
        ),
    ]


def _normalize_question(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text.lower())).strip()


def _question_is_repeat(text: str, previous_questions: list[str]) -> bool:
    normalized = _normalize_question(text)
    return any(normalized == _normalize_question(question) for question in previous_questions)


def _avoid_repeated_question(
    questions: list[str],
    order_idx: int,
    previous_questions: list[str],
) -> str:
    previous = {_normalize_question(question) for question in previous_questions}
    if not questions:
        return "Tell me about a project that best demonstrates your fit for this role."

    for offset in range(len(questions)):
        candidate = questions[(order_idx + offset) % len(questions)]
        if _normalize_question(candidate) not in previous:
            return candidate

    base = questions[order_idx % len(questions)]
    return f"Use a different example than before: {base}"


def _seed_offset(seed: str, question_count: int) -> int:
    if not seed or question_count <= 1:
        return 0

    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % question_count


def _extract_json_object(content: str) -> dict[str, Any]:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        parts = cleaned.split("```")
        if len(parts) >= 2:
            cleaned = parts[1].strip()
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].strip()

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1:
        cleaned = cleaned[start:end + 1]

    return json.loads(cleaned)


def question_payload(
    mode: str,
    job_role: str,
    order_idx: int,
    job_description: str = "",
    resume_context: str = "",
    previous_questions: list[str] | None = None,
    last_evaluation: dict[str, Any] | None = None,
    fallback_seed: str = "",
) -> dict[str, Any]:
    previous_questions = previous_questions or []
    context_questions = _context_questions(
        job_role,
        clean_job_description(job_description),
        resume_context,
    )
    questions = QUESTION_BANK.get(mode, QUESTION_BANK["faang"])
    selected_questions = context_questions or questions
    seeded_order_idx = order_idx + _seed_offset(fallback_seed, len(selected_questions))
    selected_question = _avoid_repeated_question(
        selected_questions,
        seeded_order_idx,
        previous_questions,
    )
    is_weak_answer = int(last_evaluation.get("score") or 100) < 60 if last_evaluation else False
    if is_weak_answer:
        selected_question = (
            "Let us go one level deeper on your previous answer. "
            f"{selected_question}"
        )

    return {
        "text": selected_question,
        "category": "Behavioral" if mode == "hr" else "Interview",
        "topic": job_role or "General",
        "difficulty": "warmup" if order_idx == 0 else "adaptive",
        "why_asked": (
            "Generated from the resume, pasted job description, selected interview mode, and job role."
            if context_questions
            else "Generated from the selected interview mode and job role."
        ),
        "is_weakness_focused": False,
        "order_idx": order_idx,
    }


def _fallback_question_payload(
    *,
    mode: str,
    job_role: str,
    order_idx: int,
    job_description: str,
    resume_context: str,
    previous_questions: list[str],
    last_evaluation: dict[str, Any] | None,
    topic_info: dict[str, Any] | None,
    fallback_seed: str,
) -> dict[str, Any]:
    topic = (topic_info or {}).get("topic") or job_role
    payload = question_payload(
        mode,
        topic,
        order_idx,
        job_description,
        resume_context=resume_context,
        previous_questions=previous_questions,
        last_evaluation=last_evaluation,
        fallback_seed=fallback_seed,
    )
    if topic_info:
        payload["category"] = topic_info.get("category") or payload["category"]
        payload["difficulty"] = topic_info.get("difficulty") or payload["difficulty"]
        payload["topic"] = topic_info.get("topic") or payload["topic"]
    payload["why_asked"] = f"{payload['why_asked']} Gemini was unavailable, so a local non-repeating fallback was used."
    return payload


def _build_prompt(
    *,
    mode: str,
    job_role: str,
    job_description: str,
    order_idx: int,
    previous_questions: list[str],
    last_question: str | None,
    last_answer: str | None,
    last_evaluation: dict[str, Any] | None,
    resume_context: str,
    topic_info: dict[str, Any] | None,
) -> str:
    persona = get_persona(mode)
    previous = "\n".join(f"- {question}" for question in previous_questions[-8:]) or "None yet"
    score = last_evaluation.get("score") if last_evaluation else None
    reasoning = last_evaluation.get("reasoning") or last_evaluation.get("cot_reasoning") if last_evaluation else ""
    question_type = "follow-up" if isinstance(score, (int, float)) and score < settings.weak_score_threshold else "new topic"
    topic = (topic_info or {}).get("topic") or job_role
    category = (topic_info or {}).get("category") or "Role Fit"
    difficulty = (topic_info or {}).get("difficulty") or ("warmup" if order_idx == 0 else "adaptive")
    focus = (topic_info or {}).get("focus") or ""

    return f"""You are {persona['name']}, conducting a {mode} mock interview.

Persona style: {persona.get('style', '')}
Tone: {persona.get('tone', '')}
Question style rules:
{chr(10).join('- ' + rule for rule in persona.get('question_style', []))}

Job role: {job_role}
Question number: {order_idx + 1}
Question type: {question_type}
Target topic: {topic}
Category: {category}
Difficulty: {difficulty}
Focus: {focus}

Job description:
{job_description or 'No job description provided.'}

Resume context:
{resume_context or 'No resume context provided.'}

Previous questions, do not repeat or lightly rephrase these:
{previous}

Last asked question:
{last_question or 'None'}

Candidate's last answer transcript:
{(last_answer or 'None')[:1800]}

Last evaluation:
Score: {score if score is not None else 'N/A'}
Reasoning: {(reasoning or 'N/A')[:800]}

Generate exactly one fresh interview question grounded in the candidate's resume, pasted job description, job role, and target topic.
Rules:
1. Do not repeat any previous question.
2. If the last score is weak, ask a deeper follow-up on the same weakness.
3. Otherwise, move to a new job-description requirement, resume project, target topic, or role-relevant angle.
4. Make it specific enough that the candidate cannot answer with a generic script.
5. Keep it to one question, no preamble.

Return only valid JSON:
{{
  "text": "question text",
  "category": "{category}",
  "topic": "{topic}",
  "difficulty": "{difficulty}",
  "why_asked": "one sentence",
  "is_weakness_focused": false
}}"""


def _generate_with_gemini_sync(
    *,
    mode: str,
    job_role: str,
    job_description: str,
    order_idx: int,
    previous_questions: list[str],
    last_question: str | None,
    last_answer: str | None,
    last_evaluation: dict[str, Any] | None,
    resume_context: str,
    topic_info: dict[str, Any] | None,
) -> dict[str, Any]:
    content = invoke_llm_text(
        _build_prompt(
            mode=mode,
            job_role=job_role,
            job_description=job_description,
            order_idx=order_idx,
            previous_questions=previous_questions,
            last_question=last_question,
            last_answer=last_answer,
            last_evaluation=last_evaluation,
            resume_context=resume_context,
            topic_info=topic_info,
        ),
        temperature=0.75,
        max_tokens=450,
        request_timeout=20,
        purpose="question_generation",
    )
    question = _extract_json_object(content)
    text = str(question.get("text") or "").strip()
    if not text:
        raise ValueError("Gemini returned an empty question")
    if _question_is_repeat(text, previous_questions):
        raise ValueError("Gemini repeated a previous question")

    return {
        "text": text,
        "category": str(question.get("category") or ("Behavioral" if mode == "hr" else "Interview")),
        "topic": str(question.get("topic") or job_role or "General"),
        "difficulty": str(question.get("difficulty") or ("warmup" if order_idx == 0 else "adaptive")),
        "why_asked": str(question.get("why_asked") or "Generated by Gemini from the resume, job description, and interview history."),
        "is_weakness_focused": bool(question.get("is_weakness_focused", False)),
        "order_idx": order_idx,
    }


def generate_question_payload_sync(
    *,
    mode: str,
    job_role: str,
    order_idx: int,
    job_description: str = "",
    previous_questions: list[str] | None = None,
    last_question: str | None = None,
    last_answer: str | None = None,
    last_evaluation: dict[str, Any] | None = None,
    resume_context: str = "",
    topic_info: dict[str, Any] | None = None,
    fallback_seed: str = "",
) -> dict[str, Any]:
    previous_questions = previous_questions or []

    try:
        payload = _generate_with_gemini_sync(
            mode=mode,
            job_role=job_role,
            job_description=job_description,
            order_idx=order_idx,
            previous_questions=previous_questions,
            last_question=last_question,
            last_answer=last_answer,
            last_evaluation=last_evaluation,
            resume_context=resume_context,
            topic_info=topic_info,
        )
        logger.info(
            "question_generated_with_gemini",
            model=settings.primary_llm,
            order_idx=order_idx,
            topic=payload.get("topic"),
        )
        return payload
    except Exception as e:
        logger.warning(
            "gemini_question_generation_failed",
            model=settings.primary_llm,
            order_idx=order_idx,
            error=str(e),
        )
        return _fallback_question_payload(
            mode=mode,
            job_role=job_role,
            order_idx=order_idx,
            job_description=job_description,
            resume_context=resume_context,
            previous_questions=previous_questions,
            last_evaluation=last_evaluation,
            topic_info=topic_info,
            fallback_seed=fallback_seed,
        )


async def generate_question_payload(
    *,
    mode: str,
    job_role: str,
    order_idx: int,
    job_description: str = "",
    previous_questions: list[str] | None = None,
    last_question: str | None = None,
    last_answer: str | None = None,
    last_evaluation: dict[str, Any] | None = None,
    resume_context: str = "",
    topic_info: dict[str, Any] | None = None,
    fallback_seed: str = "",
) -> dict[str, Any]:
    return await asyncio.to_thread(
        generate_question_payload_sync,
        mode=mode,
        job_role=job_role,
        order_idx=order_idx,
        job_description=job_description,
        previous_questions=previous_questions,
        last_question=last_question,
        last_answer=last_answer,
        last_evaluation=last_evaluation,
        resume_context=resume_context,
        topic_info=topic_info,
        fallback_seed=fallback_seed,
    )


def _expanded_plan(interview_plan: list[dict]) -> list[dict]:
    expanded = []
    for item in interview_plan:
        count = item.get("count", 1)
        try:
            count = max(1, int(count))
        except (TypeError, ValueError):
            count = 1
        expanded.extend([item] * count)
    return expanded


def _get_next_topic(state: InterviewState) -> dict:
    """Determine the next topic to ask about, with weakness bias."""
    current_index = state.get("current_index", 0)
    interview_plan = _expanded_plan(state.get("interview_plan", []))
    weak_topics = state.get("weak_topics", [])

    if current_index < len(interview_plan):
        return interview_plan[current_index]

    if weak_topics and random.random() < 0.7:
        return {
            "category": "Weakness Focus",
            "topic": random.choice(weak_topics),
            "difficulty": state.get("difficulty", "medium"),
            "focus": "addressing weakness",
        }

    return {
        "category": "General",
        "topic": state.get("job_role", ""),
        "difficulty": "medium",
        "focus": "general",
    }


def _question_texts(questions: list[dict]) -> list[str]:
    return [
        str(question.get("text") or "")
        for question in questions
        if question.get("text")
    ]


def generator_agent(state: InterviewState) -> dict:
    """
    Generate the next interview question using the shared Gemini-backed
    question generator used by the backend API.
    """
    topic_info = _get_next_topic(state)
    questions = state.get("questions", [])
    answers = state.get("answers", [])
    evaluations = state.get("evaluations", [])
    retrieved_chunks = state.get("retrieved_chunks", [])
    resume_summary = state.get("resume_summary", {})

    retrieved_context = "\n".join(
        chunk.get("chunk_text", "")
        for chunk in retrieved_chunks[:3]
    )[:2000]
    resume_context = (
        retrieved_context
        or json.dumps(resume_summary, ensure_ascii=True)[:2000]
    )
    last_question = questions[-1].get("text") if questions else None
    last_answer = answers[-1].get("transcript") if answers else None
    last_evaluation = evaluations[-1] if evaluations else None

    question_data = generate_question_payload_sync(
        mode=state.get("interview_mode", "faang"),
        job_role=state.get("job_role", "") or topic_info.get("topic", ""),
        order_idx=len(questions),
        job_description=state.get("job_description", ""),
        previous_questions=_question_texts(questions),
        last_question=last_question,
        last_answer=last_answer,
        last_evaluation=last_evaluation,
        resume_context=resume_context,
        topic_info=topic_info,
        fallback_seed=state.get("interview_id") or state.get("resume_id", ""),
    )

    if topic_info.get("topic") in state.get("weak_topics", []):
        question_data["is_weakness_focused"] = True

    logger.info(
        "question_generated",
        topic=question_data.get("topic"),
        difficulty=question_data.get("difficulty"),
        weakness_focused=question_data.get("is_weakness_focused"),
        model=settings.primary_llm,
    )

    return {"questions": questions + [question_data]}
