"""Quiz question generators (AI and math).

Provides:
- async generate_ai_questions(topic: str, n: int) -> list[QuizQuestion]
- generate_math_questions(...): list[QuizQuestion]

Uses pydantic-ai and provider selection similar to video_generator agents.
"""

from __future__ import annotations

import random
from typing import Iterable

from pydantic import BaseModel, Field
from pydantic_ai import Agent

from app.core.config import settings
from app.modules.quiz.models import QuizQuestion


class QuizQuestionSet(BaseModel):
    """Structured output for MCQ generation."""

    questions: list[QuizQuestion] = Field(default_factory=list)


def _build_google_model():
    """Build Google Gemini model for pydantic-ai (lazy import)."""
    from pydantic_ai.models.google import GoogleModel
    from pydantic_ai.providers.google import GoogleProvider

    provider = GoogleProvider(api_key=settings.gemini_api_key)
    return GoogleModel("gemini-2.5-flash", provider=provider)


def _build_openrouter_model():
    """Build OpenRouter model via OpenAI-compatible provider (lazy import)."""
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.openai import OpenAIProvider

    if not settings.openrouter_api_key:
        raise RuntimeError(
            "OpenRouter API key not configured. Set OPENROUTER_API_KEY in your environment."
        )

    provider = OpenAIProvider(
        api_key=settings.openrouter_api_key,
        base_url="https://openrouter.ai/api/v1",
    )
    model_name = settings.openrouter_model
    return OpenAIChatModel(model_name, provider=provider)


def _build_model_by_settings():
    provider = (settings.model_provider or "google").lower()
    if provider == "openrouter":
        return _build_openrouter_model()
    return _build_google_model()


SYSTEM_PROMPT = (
    "You are an expert quiz author. Generate high-quality MULTIPLE-CHOICE questions. "
    "Return a JSON object that validates as QuizQuestionSet: {questions}. "
    "Each question has: {question, choices, correct_index}. Rules: "
    "- Create exactly N questions (provided in the instruction). "
    "- Each question must have EXACTLY 4 concise choices (plain text). "
    "- correct_index is a 0-based integer index into the choices array. "
    "- Avoid markdown; do not include code fences."
)


def _build_instruction(topic: str, n: int) -> str:
    return (
        "Create N multiple-choice questions for the topic below. "
        "Return only the JSON object.\n\n"
        f"Topic: {topic}\n"
        f"N: {int(n)}\n"
        "Audience: general, varied difficulty."
    )


async def generate_ai_questions(topic: str, n: int = 10) -> list[QuizQuestion]:
    """Generate MCQs using the configured model provider."""
    model = _build_model_by_settings()
    agent: Agent[None, QuizQuestionSet] = Agent[None, QuizQuestionSet](
        model=model,
        output_type=QuizQuestionSet,
        system_prompt=SYSTEM_PROMPT,
        retries=2,
    )
    res = await agent.run(_build_instruction(topic, n))
    # Post-process: trim to n, ensure valid indices and 4 choices
    out: list[QuizQuestion] = []
    for q in res.output.questions[:n]:
        choices = [str(c).strip() for c in (q.choices or []) if str(c).strip()]
        if len(choices) < 2:
            # Skip malformed
            continue
        # normalize to 4 choices if possible
        if len(choices) > 4:
            choices = choices[:4]
        elif len(choices) < 4:
            # pad with plausible distractors (very basic fallback)
            while len(choices) < 4:
                choices.append(f"Option {len(choices) + 1}")
        idx = int(q.correct_index)
        if idx < 0 or idx >= len(choices):
            idx = 0
        out.append(
            QuizQuestion(
                question=q.question.strip(), choices=choices, correct_index=idx
            )
        )
    return out[:n]


def _rand_int(a: int, b: int) -> int:
    return random.randint(a, b)


def _gen_add(min_v: int, max_v: int) -> tuple[str, list[str], int]:
    a = _rand_int(min_v, max_v)
    b = _rand_int(min_v, max_v)
    ans = a + b
    correct = str(ans)
    distractors = {str(ans + d) for d in (-2, -1, 1, 2)}
    distractors.discard(correct)
    opts = list(distractors)
    while len(opts) < 3:
        opts.append(str(ans + _rand_int(-10, 10)))
    all_opts = [correct] + opts[:3]
    random.shuffle(all_opts)
    return f"{a} + {b} = ?", all_opts, all_opts.index(correct)


def _gen_div(
    min_v: int, max_v: int, integer_only: bool = True
) -> tuple[str, list[str], int]:
    b = _rand_int(max(min_v, 1), max_v)
    if integer_only:
        # construct divisible pair
        ans = _rand_int(min_v, max_v // max(b, 1)) or 1
        a = ans * b
    else:
        a = _rand_int(min_v, max_v)
        ans = a / b
    correct = str(ans)
    distractors = {str(ans + d) for d in (-2, -1, 1, 2)}
    distractors.discard(correct)
    opts = list(distractors)
    while len(opts) < 3:
        opts.append(
            str((ans if isinstance(ans, int) else round(ans, 2)) + _rand_int(-5, 5))
        )
    all_opts = [correct] + opts[:3]
    random.shuffle(all_opts)
    return f"{a} ÷ {b} = ?", all_opts, all_opts.index(correct)


def generate_math_questions(
    *,
    num_questions: int = 10,
    min_value: int = 1,
    max_value: int = 99,
    ops: Iterable[str] = ("add", "div"),
    division_integer_only: bool = True,
) -> list[QuizQuestion]:
    """Generate simple arithmetic MCQs (addition/division only)."""
    ops_list = [o for o in ops if o in ("add", "div")] or ["add", "div"]
    out: list[QuizQuestion] = []
    for _ in range(max(1, int(num_questions))):
        op = random.choice(ops_list)
        if op == "add":
            q, ch, idx = _gen_add(min_value, max_value)
        else:
            q, ch, idx = _gen_div(min_value, max_value, division_integer_only)
        out.append(QuizQuestion(question=q, choices=ch, correct_index=idx))
    return out
