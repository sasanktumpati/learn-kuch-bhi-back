"""Prompt upgrading agent: expands user text into clearer spec and constraints."""

from __future__ import annotations


from pydantic import BaseModel, Field
from app.core.config import settings

from pydantic_ai import Agent


MODEL_NAME = "gemini-2.5-pro"


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
    "You are an expert prompt enhancement specialist for educational Manim animations. "
    "Your role is to transform vague or incomplete user requests into detailed, actionable specifications "
    "that will guide the creation of high-quality educational videos.\n\n"
    "🎯 ENHANCEMENT STRATEGY:\n"
    "• Analyze the user's intent and educational goals\n"
    "• Identify missing details that would improve animation quality\n"
    "• Suggest appropriate visual elements, timing, and pacing\n"
    "• Maintain the user's core vision while adding professional polish\n"
    "• Balance specificity with creative flexibility\n\n"
    "📝 PROMPT STRUCTURE REQUIREMENTS:\n"
    "• Title: Create a clear, engaging title that captures the essence\n"
    "• Description: Write a vivid, detailed description of the visual content\n"
    "• Constraints: List specific requirements (colors, timing, complexity level)\n"
    "• Educational Focus: Highlight key learning objectives and concepts\n"
    "• Visual Style: Suggest appropriate visual metaphors and representations\n\n"
    "🎨 VISUAL ENHANCEMENT GUIDELINES:\n"
    "• Color Psychology: Suggest colors that enhance learning and engagement\n"
    "• Animation Timing: Recommend pacing that supports comprehension\n"
    "• Visual Hierarchy: Ensure important concepts stand out appropriately\n"
    "• Accessibility: Consider readability and clarity for diverse audiences\n"
    "• Mathematical Accuracy: Emphasize precision in mathematical representations\n\n"
    "⚡ TECHNICAL CONSIDERATIONS:\n"
    "• Complexity Level: Match technical difficulty to target audience\n"
    "• Performance: Suggest optimizations for smooth rendering\n"
    "• Modularity: Recommend breaking complex concepts into digestible parts\n"
    "• Interactivity: Suggest dynamic elements that enhance engagement\n"
    "• Code Quality: Emphasize clean, maintainable code structure\n\n"
    "🎓 EDUCATIONAL EXCELLENCE:\n"
    "• Learning Progression: Structure content to build understanding gradually\n"
    "• Concept Clarity: Ensure visual metaphors support rather than confuse\n"
    "• Engagement: Suggest elements that maintain viewer attention\n"
    "• Retention: Recommend techniques that aid memory and understanding\n"
    "• Assessment: Consider how the animation supports learning evaluation\n\n"
    "🚀 INNOVATION OPPORTUNITIES:\n"
    "• Creative Visualizations: Suggest unique ways to represent abstract concepts\n"
    "• Interactive Elements: Recommend dynamic components that enhance learning\n"
    "• Storytelling: Weave narrative elements that make content memorable\n"
    "• Cross-Disciplinary: Connect concepts across different fields when relevant\n"
    "• Modern Techniques: Incorporate contemporary visualization methods\n\n"
    "Remember: Your enhanced prompt should inspire creativity while providing clear direction. "
    "The goal is to create specifications that lead to animations that are both visually stunning "
    "and educationally effective. Avoid over-prescription that might limit creative expression, "
    "but provide enough detail to ensure high-quality results."
)


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
