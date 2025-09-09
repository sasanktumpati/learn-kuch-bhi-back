from __future__ import annotations


from pydantic import BaseModel, Field
from typing import cast
from pydantic_ai import Agent
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider

from app.core.config import settings


MODEL_NAME = "gemini-2.5-pro"


def _build_google_model() -> GoogleModel:
    api_key = settings.gemini_api_key
    provider = GoogleProvider(api_key=api_key)
    return GoogleModel(
        MODEL_NAME,
        provider=provider,
    )


class UpgradedPrompt(BaseModel):
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
    "avoid over-prescription. Keep it concise yet complete."
)


def build_prompt_upgrader() -> Agent[UpgradedPrompt, str]:
    model = _build_google_model()
    agent: Agent[UpgradedPrompt, str] = Agent[UpgradedPrompt, str](
        model, output_type=UpgradedPrompt, system_prompt=SYSTEM_PROMPT
    )
    return agent


def upgrade_prompt_sync(user_prompt: str) -> UpgradedPrompt:
    agent: Agent[UpgradedPrompt, str] = build_prompt_upgrader()
    return cast(UpgradedPrompt, agent.run_sync(user_prompt).output)


async def upgrade_prompt(user_prompt: str) -> UpgradedPrompt:
    """Async variant for use inside running event loops.

    Avoids nested event loop errors by using the agent's async API.
    """
    agent: Agent[UpgradedPrompt, str] = build_prompt_upgrader()
    res = await agent.run(user_prompt)
    return cast(UpgradedPrompt, res.output)
