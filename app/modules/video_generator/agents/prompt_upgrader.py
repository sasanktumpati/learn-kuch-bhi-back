"""Prompt upgrading agent: expands user text into clearer spec and constraints."""

from __future__ import annotations


from pydantic import BaseModel, Field
from app.core.config import settings

from pydantic_ai import Agent


MODEL_NAME = "gemini-flash-latest"


def _build_google_model():
    from pydantic_ai.models.google import GoogleModel
    from pydantic_ai.providers.google import GoogleProvider

    api_key = settings.gemini_api_key
    provider = GoogleProvider(api_key=api_key)
    return GoogleModel(MODEL_NAME, provider=provider)


class UpgradedPrompt(BaseModel):
    """Normalized, more descriptive prompt the codegen consumes."""

    title: str = Field(..., description="Short, clear title for the video")
    description: str = Field(
        ..., description="Expanded, vivid description of the content"
    )
    constraints: list[str] = Field(
        default_factory=list, description="Explicit constraints or must-haves"
    )


SYSTEM_PROMPT = """
You are a prompt refinement specialist for educational Manim animations.
Transform short, vague, or messy requests into a precise, useful brief the
code generator can act on immediately.

Goals
- Preserve the user’s intent; remove ambiguity with concrete detail.
- Add constraints that improve clarity, readability, and pacing.
- Be specific but not prescriptive; describe “what” to show, not code.

Output Schema (UpgradedPrompt)
- Title: Short, clear, and specific (≤ 10 words).
- Description: 3–7 concise sentences describing the visuals, flow, and
  emphasis. Focus on what the viewer sees and learns.
- Constraints: List of short, actionable requirements (one idea per item).

What to include in Constraints (when applicable)
- Target audience and difficulty (e.g., “grade 10”, “introductory calculus”).
- Visual elements (e.g., axes, arrows, highlights, labels, color roles).
- Layout and frame safety (keep all content within frame, no overlaps, maintain safe margins).
- Timing and pacing (approximate duration, pauses between steps).
- Style preferences (minimalist, clean palette, subdued background).
- Assumptions when the prompt is ambiguous (state them explicitly).

Style
- Plain English. No emojis, markdown, or code.
- No API names, Manim classes, or implementation details.
- Avoid marketing language; be factual and unambiguous.

Return only the fields of UpgradedPrompt; no extra commentary.
"""


def build_prompt_upgrader():
    model = _build_google_model()
    agent: Agent[None, UpgradedPrompt] = Agent[None, UpgradedPrompt](
        model,
        output_type=UpgradedPrompt,
        system_prompt=SYSTEM_PROMPT,
        # Retry a few times to improve validated structured output
        retries=3,
    )
    return agent


def upgrade_prompt_sync(user_prompt: str) -> UpgradedPrompt:
    agent: "Agent[None, UpgradedPrompt]" = build_prompt_upgrader()
    return agent.run_sync(user_prompt).output


async def upgrade_prompt(user_prompt: str) -> UpgradedPrompt:
    """Async variant for use inside running event loops."""
    agent: "Agent[None, UpgradedPrompt]" = build_prompt_upgrader()
    res = await agent.run(user_prompt)
    return res.output
