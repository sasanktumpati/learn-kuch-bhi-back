"""Prompt upgrading agent: expands user text into clearer spec and constraints."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field
from app.core.config import settings

if TYPE_CHECKING:
    from pydantic_ai import Agent


MODEL_NAME = "gemini-2.5-flash"


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


SYSTEM_PROMPT = (
    "You are a helpful assistant improving user prompts for Manim animations. "
    "Rewrite the prompt to be specific and descriptive. "
    "Add any useful constraints (colors, timing, pacing, camera moves) but "
    "avoid over-prescription. Keep it concise yet complete. If code is later "
    "generated, it must use explicit imports (no star imports)."
)


def build_prompt_upgrader():
    from pydantic_ai import Agent

    model = _build_google_model()
    agent: Agent[None, UpgradedPrompt] = Agent[None, UpgradedPrompt](
        model, output_type=UpgradedPrompt, system_prompt=SYSTEM_PROMPT
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
