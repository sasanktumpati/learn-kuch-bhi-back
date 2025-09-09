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


class MultiFlashcardsGenerator:
    """Orchestrates an outline agent and per-subtopic flashcard agents."""

    def __init__(self, *, concurrency: int = 6) -> None:
        self.concurrency = max(1, int(concurrency))

    async def generate(
        self,
        base_prompt: str,
    ) -> MultiFlashcardsResult:
        outline = await generate_outline(base_prompt)

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
    ) -> "MultiFlashcardsResult":
        """Generate multi-flashcards; persist outline, placeholder sets, and fill them progressively."""
        from app.core.db_services import FlashcardGenerationService

        outline = await generate_outline(base_prompt)

        db_service = FlashcardGenerationService(session)
        db_run = await db_service.create_multi_result_processing(
            user_id=user_id,
            outline_json=outline.model_dump(),
            original_prompt=base_prompt,
            concurrency_setting=self.concurrency,
        )

        subtopic_index = await db_service.create_topics_and_subtopics(
            multi_result_id=db_run.id,
            outline=outline,
        )

        for t in outline.topics or []:
            for s in t.subtopics or []:
                sub_id = subtopic_index.get((t.name, s.name))
                if not sub_id:
                    continue

                placeholder = await db_service.create_placeholder_flashcard_set(
                    user_id=user_id,
                    multi_result_id=db_run.id,
                    subtopic_id=sub_id,
                    original_prompt=f"{base_prompt} - {t.name}: {s.name}",
                    title=f"{t.name} — {s.name}",
                    description="Generating...",
                    tags=[],
                )

                prompt = (
                    f"Generate a sensible, study-friendly number of high-quality flashcards for "
                    f"the subtopic '{s.name}' under the topic '{t.name}'. "
                    f"Overall subject: {base_prompt}. "
                    "Audience: undergrad-friendly, precise. "
                    "No markdown; plain text questions and answers."
                )
                fc = await generate_flashcards(prompt)

                await db_service.finalize_flashcard_set(
                    set_id=placeholder.id, pydantic_set=fc
                )

        from app.core.db.schemas.flashcards import GenerationStatus as FCStatus

        await db_service.update_multi_result_status(
            multi_result_id=db_run.id,
            status=FCStatus.COMPLETED,
            completed_at=__import__("datetime").datetime.now(),
        )

        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        from app.core.db.schemas.flashcards import (
            MultiFlashcardsResult as DBRun,
            Topic as DBTopic,
        )

        result = await session.execute(
            select(DBRun)
            .options(
                selectinload(DBRun.flashcard_sets),
                selectinload(DBRun.topics).selectinload(DBTopic.subtopics),
            )
            .where(DBRun.id == db_run.id)
        )
        return result.scalar_one()

    def generate_sync(
        self,
        base_prompt: str,
    ) -> MultiFlashcardsResult:
        import asyncio

        return asyncio.run(self.generate(base_prompt))
