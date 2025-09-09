"""Flashcard generator using pydantic-ai and Gemini provider.

This module exposes a simple async function that returns a validated
``FlashcardSet`` given a user prompt/topic. Imports for the LLM provider are
kept lazy to avoid import-time errors when credentials are missing.
"""

from __future__ import annotations

from pydantic_ai import Agent

from app.core.config import settings
from app.modules.flashcards.models.flashcards import FlashcardSet
from app.modules.flashcards.models.outline import TopicOutline

OUTLINE_MODEL_NAME = "gemini-2.5-pro"
FLASHCARDS_MODEL_NAME = "gemini-2.0-flash"


def _build_google_model(model_name: str, *, thinking_budget: int | None = None):
    """Build the Google Gemini model provider (lazy import).

    thinking_budget is only applied when provided; useful for flash-lite.
    """
    from pydantic_ai.models.google import GoogleModel, GoogleModelSettings
    from pydantic_ai.providers.google import GoogleProvider

    api_key = settings.gemini_api_key
    provider = GoogleProvider(api_key=api_key)
    settings_obj = None
    if thinking_budget is not None:
        settings_obj = GoogleModelSettings(
            google_thinking_config={"thinking_budget": thinking_budget}
        )
    return GoogleModel(model_name, provider=provider, settings=settings_obj)


SYSTEM_PROMPT = (
    "You are an expert educator who crafts focused, accurate flashcards. "
    "Return a single JSON object that validates as the provided Pydantic "
    "FlashcardSet model: {title, description, tags, flashcards}. "
    "Rules: "
    "- Title: short and specific. "
    "- Description: 1–2 sentences describing scope. "
    "- Tags: 3–7 short lowercase keywords, no punctuation. "
    "- Flashcards: a list of question/answer pairs (plain text, no markdown). "
    "  Each question is clear and atomic; each answer concise (2–6 sentences). "
    "  Prefer conceptual understanding over trivia; include varied difficulty. "
    "- Count: aim for 10–20 cards by default, but adapt to topic complexity "
    "  and keep within 1–100. "
    "- No extra keys or commentary; do not include code fences."
)


def _build_instruction(user_prompt: str) -> str:
    return (
        "Create a cohesive flashcard set for the topic below. "
        "Follow the system rules and output only the JSON object.\n\n"
        f"Topic or instructions: {user_prompt}"
    )


OUTLINE_SYSTEM_PROMPT = (
    "You design clean, pragmatic learning outlines (topics and subtopics). "
    "Return a JSON object matching the TopicOutline model: {title, topics}. "
    "Each topic has {name, subtopics}; each subtopic has {name, optional description}. "
    "Decide how many topics and subtopics make sense for the subject: ensure good coverage "
    "without being overwhelming. Aim for a manageable, study-friendly outline (e.g., total "
    "subtopics often in the range of 8–20) but adapt to the prompt. Keep names short and specific; "
    "descriptions at most one sentence. No extra fields or commentary."
)


def _outline_instruction(base_prompt: str) -> str:
    return (
        "Create a concise, study-friendly learning outline for the subject below. "
        "Choose the number of topics and subtopics based on the subject's breadth and difficulty.\n\n"
        f"Subject/instructions: {base_prompt}\n"
        "Audience: undergrad-friendly, precise terminology."
    )


async def generate_outline(base_prompt: str) -> TopicOutline:
    model = _build_google_model(OUTLINE_MODEL_NAME)
    agent: Agent[None, TopicOutline] = Agent[None, TopicOutline](
        model=model,
        output_type=TopicOutline,
        system_prompt=OUTLINE_SYSTEM_PROMPT,
        retries=3,
    )
    instr = _outline_instruction(base_prompt)
    res = await agent.run(instr)
    return res.output


async def generate_flashcards(user_prompt: str) -> FlashcardSet:
    """Generate and validate a FlashcardSet from the given prompt."""
    model = _build_google_model(FLASHCARDS_MODEL_NAME, thinking_budget=0)
    agent: Agent[None, FlashcardSet] = Agent[None, FlashcardSet](
        model=model,
        output_type=FlashcardSet,
        system_prompt=SYSTEM_PROMPT,
        retries=3,
    )
    instruction = _build_instruction(user_prompt)
    res = await agent.run(instruction)
    return _postprocess(res.output)


def generate_flashcards_sync(user_prompt: str) -> FlashcardSet:
    """Synchronous wrapper if an event loop is unavailable."""
    model = _build_google_model(FLASHCARDS_MODEL_NAME, thinking_budget=0)
    agent: Agent[None, FlashcardSet] = Agent[None, FlashcardSet](
        model=model,
        output_type=FlashcardSet,
        system_prompt=SYSTEM_PROMPT,
        retries=3,
    )
    instruction = _build_instruction(user_prompt)
    res = agent.run_sync(instruction)
    return _postprocess(res.output)


def _postprocess(fc: FlashcardSet) -> FlashcardSet:
    """Light normalization without adding complex provider constraints."""
    title = (fc.title or "").strip() or "Flashcards"
    desc = (fc.description or "").strip() or f"A set of flashcards about {title}."
    tags = []
    for t in fc.tags or []:
        s = str(t).strip().lower()
        if s and s not in tags:
            tags.append(s)

    tags = tags[:10]

    clean_cards = []
    for c in fc.flashcards or []:
        q = (c.question or "").strip()
        a = (c.answer or "").strip()
        if q and a:
            clean_cards.append(type(c)(question=q, answer=a))

    clean_cards = clean_cards[:100]

    return type(fc)(title=title, description=desc, tags=tags, flashcards=clean_cards)
