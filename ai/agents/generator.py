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
        "To start, give me a concise overview of your background and the project on your resume that best matches this role.",
        "Walk me through one technically challenging project from your resume. What trade-offs did you make, and how did you validate the result?",
        "Describe a difficult bug or performance issue you solved. How did you isolate the root cause?",
        "Let's run a system design case. Design a service for a realistic product workflow in this role, including requirements, APIs, data model, scaling bottlenecks, and failure handling.",
        "Tell me about a time you disagreed on a technical direction. What did you do, and what changed?",
        "Before we close, what would you ask the team to understand whether this role is a strong fit?",
    ],
    "startup": [
        "To start, what kind of product work energizes you, and why is this role interesting right now?",
        "Tell me about a product or feature you shipped under constraints. What did you prioritize, and what would you improve now?",
        "Let's do a product case. A key metric drops after launch. How would you diagnose the issue, prioritize fixes, and communicate the plan?",
        "Design the smallest reliable technical solution you would ship first for this role. What would you defer?",
        "Describe a moment when you took ownership beyond your assigned role.",
        "Before we wrap, what would you ask a founder to understand whether this is the right company for you?",
    ],
    "hr": [
        "To start, tell me about your background and what attracted you to this role.",
        "Which experience from your resume best connects to this job description, and why?",
        "Tell me about a time you handled conflict with a teammate or stakeholder.",
        "Describe a failure or setback. What did you learn, and what changed afterward?",
        "What kind of work environment helps you do your best work, and where do you struggle?",
        "What questions do you have about the role, team, culture, or next steps?",
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


def _phase_key(topic_info: dict[str, Any] | None) -> str:
    if not topic_info:
        return ""
    text = " ".join(
        str(topic_info.get(key, ""))
        for key in ("phase", "category", "topic", "focus", "question_type")
    ).lower()
    if "closing" in text or "candidate question" in text:
        return "closing"
    if "opening" in text or "introduction" in text:
        return "opening"
    if "system" in text or "architecture" in text:
        return "system_design"
    if "case" in text or "product" in text:
        return "case_study"
    if "behavior" in text or "conflict" in text or "team" in text:
        return "behavioral"
    if "resume" in text or "project" in text or "experience" in text or "shipping" in text:
        return "resume_deep_dive"
    if "technical" in text or "debug" in text or "performance" in text:
        return "technical_depth"
    return ""


def _phase_questions(
    *,
    mode: str,
    job_role: str,
    job_description: str,
    resume_context: str,
    topic_info: dict[str, Any] | None,
) -> list[str]:
    phase = _phase_key(topic_info)
    if not phase:
        return []

    role = job_role or "this role"
    topic = (topic_info or {}).get("topic") or role
    focus = (topic_info or {}).get("focus") or _human_join(
        job_description_terms(f"{job_description} {resume_context}")
    )
    signal = (topic_info or {}).get("success_signal") or "clear hiring signal"
    focus_clause = f" around {focus}" if focus else ""

    if phase == "opening":
        return [
            f"To start, give me a two-minute overview of your background and why {role} is the right next step.",
            f"Before we go deeper, which project or experience from your resume should I use as the anchor for this {role} interview?",
        ]
    if phase == "resume_deep_dive":
        return [
            f"Let's go deep on {topic}. What was the problem, what did you personally own, and how did you know the result worked?",
            f"Pick the resume project most relevant to {role}{focus_clause}. Walk me through the hardest technical decision and the trade-off you chose.",
            f"When you worked on {topic}, what failed or surprised you, and how did that change your implementation?",
        ]
    if phase == "technical_depth":
        return [
            f"Let's drill into {topic}. What edge cases or performance limits would you test before trusting your solution in production?",
            f"Suppose {topic} starts failing intermittently in production. How would you isolate the root cause and prove the fix?",
            f"What is the most important technical trade-off in {topic}{focus_clause}, and what alternative would you reject?",
        ]
    if phase == "system_design":
        return [
            f"System design case: design {topic} for a real {role} team. Start by clarifying requirements, then cover APIs, data model, scaling bottlenecks, reliability, observability, and rollout.",
            f"Imagine {topic} must support 10x growth with strict reliability needs. What architecture would you propose, where would it fail first, and how would you validate it?",
            f"Design a production-ready approach for {topic}{focus_clause}. What would you build first, what would you defer, and what metrics would tell you it is working?",
        ]
    if phase == "case_study":
        return [
            f"Case study: {topic}. Walk me through how you would frame the problem, choose priorities, define success metrics, and de-risk the first release.",
            f"A stakeholder asks you to solve {topic}{focus_clause} in two weeks. What would you ship, what would you explicitly not ship, and how would you communicate the trade-offs?",
            f"Let's make this practical: for {topic}, what data would you inspect first, what hypotheses would you test, and what decision would you make if the data is inconclusive?",
        ]
    if phase == "behavioral":
        return [
            f"Tell me about a real situation where you had to demonstrate {signal}. What was the situation, what did you do, and what changed afterward?",
            f"Describe a time you had conflict or disagreement while working on something related to {role}. How did you handle it?",
            f"Give me an example where you received hard feedback. What did you change in your next project?",
        ]
    if phase == "closing":
        if mode == "startup":
            return [
                "Before we wrap, what would you ask me about the product, users, runway, team, and success expectations?",
                f"What would you need to learn in your first week to decide where you can create the most leverage as a {role}?",
            ]
        if mode == "hr":
            return [
                "Before we close, what questions do you have about the role, team culture, interview process, or next steps?",
                f"What would help you decide whether this {role} opportunity is the right environment for you?",
            ]
        return [
            "Before we close, what would you ask the hiring team about architecture, ownership, roadmap, or success expectations?",
            f"What would you want to clarify about the {role} role before joining?",
        ]
    return []


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
    topic_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    previous_questions = previous_questions or []
    phase_questions = _phase_questions(
        mode=mode,
        job_role=job_role,
        job_description=clean_job_description(job_description),
        resume_context=resume_context,
        topic_info=topic_info,
    )
    context_questions = _context_questions(
        job_role,
        clean_job_description(job_description),
        resume_context,
    )
    questions = QUESTION_BANK.get(mode, QUESTION_BANK["faang"])
    selected_questions = phase_questions or context_questions or questions
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
        "topic": (topic_info or {}).get("topic") or job_role or "General",
        "difficulty": "warmup" if order_idx == 0 else "adaptive",
        "why_asked": (
            "Generated from the current realistic interview stage, resume, pasted job description, selected interview mode, and job role."
            if phase_questions
            else
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
    payload = question_payload(
        mode,
        job_role,
        order_idx,
        job_description,
        resume_context=resume_context,
        previous_questions=previous_questions,
        last_evaluation=last_evaluation,
        fallback_seed=fallback_seed,
        topic_info=topic_info,
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
    phase = (topic_info or {}).get("phase") or _phase_key(topic_info) or "adaptive"
    focus = (topic_info or {}).get("focus") or ""
    success_signal = (topic_info or {}).get("success_signal") or "clear hiring signal"
    behaviors = "\n".join(
        f"- {behavior}" for behavior in persona.get("interviewer_behaviors", [])
    ) or "- Ask realistic follow-ups based on the candidate's answer"
    flow = "\n".join(
        f"- {step.get('phase')}: {step.get('goal')}"
        for step in persona.get("interview_flow", [])
    ) or "- Adaptive interview flow"

    return f"""You are {persona['name']}, conducting a {mode} mock interview.

Persona style: {persona.get('style', '')}
Tone: {persona.get('tone', '')}
Question style rules:
{chr(10).join('- ' + rule for rule in persona.get('question_style', []))}

Interviewer behaviors:
{behaviors}

Overall interview progression:
{flow}

Job role: {job_role}
Question number: {order_idx + 1}
Current interview stage: {phase}
Question type: {question_type}
Target topic: {topic}
Category: {category}
Difficulty: {difficulty}
Focus: {focus}
Success signal to test: {success_signal}

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

Generate exactly one fresh interview question grounded in the candidate's resume, pasted job description, job role, current interview stage, and target topic.
Rules:
1. Do not repeat any previous question.
2. Make it sound like a real interviewer speaking live, not a written exam.
3. If this is a system design, architecture, or case-study stage, include realistic constraints and ask the candidate to clarify requirements, reason through trade-offs, and define validation metrics.
4. If this is a resume deep dive, ask for ownership, decisions, mistakes, trade-offs, and measurable validation.
5. If this is a behavioral stage, ask for a concrete STAR example and one reflection.
6. If the last score is weak, ask a deeper follow-up on the same weakness.
7. Keep it to one question, no preamble.

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
