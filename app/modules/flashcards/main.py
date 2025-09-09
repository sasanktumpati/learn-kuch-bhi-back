"""Flashcards service class and simple module entrypoint.

Provides a high-level class for generating validated flashcard sets that can be
used in API handlers or background jobs. Mirrors the pattern from the video
generator for a consistent developer experience.
"""

from __future__ import annotations


from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.flashcards.generator import (
    generate_flashcards,
    generate_outline,
)
from app.modules.flashcards.models.outline import (
    MultiFlashcardsResult,
    SubtopicFlashcards,
)
# Imports moved to method level to avoid circular imports


class MultiFlashcardsGenerator:
    """Orchestrates an outline agent and per-subtopic flashcard agents."""

    def __init__(self, *, concurrency: int = 6) -> None:
        self.concurrency = max(1, int(concurrency))

    async def generate(
        self,
        base_prompt: str,
    ) -> MultiFlashcardsResult:
        outline = await generate_outline(base_prompt)

        # Generate flashcards for subtopics sequentially
        results: list[SubtopicFlashcards] = []

        for t in outline.topics or []:
            for s in t.subtopics or []:
                prompt = (
                    f"Generate a sensible, study-friendly number of high-quality flashcards for "
                    f"the subtopic '{s.name}' under the topic '{t.name}'. "
                    f"Overall subject: {base_prompt}. "
                    "Audience: undergrad-friendly, precise. "
                    "No markdown; plain text questions and answers."
                )
                fc = await generate_flashcards(prompt)
                results.append(
                    SubtopicFlashcards(topic=t.name, subtopic=s.name, flashcard_set=fc)
                )

        return MultiFlashcardsResult(outline=outline, sets=results)

    async def generate_with_db(
        self,
        session: AsyncSession,
        user_id: int,
        base_prompt: str,
    ) -> "MultiFlashcardsResult":  # Returns DB model
        """Generate multi-flashcards with outline and store everything in database."""
        from app.core.db_services import FlashcardGenerationService

        # Generate the multi-flashcards result
        pydantic_result = await self.generate(base_prompt)

        # Store in database with proper relationships
        db_service = FlashcardGenerationService(session)
        db_result = await db_service.save_multi_flashcards_result(
            user_id=user_id,
            multi_result=pydantic_result,
            original_prompt=base_prompt,
            concurrency_setting=self.concurrency,
        )

        return db_result

    def generate_sync(
        self,
        base_prompt: str,
    ) -> MultiFlashcardsResult:
        import asyncio

        return asyncio.run(self.generate(base_prompt))
