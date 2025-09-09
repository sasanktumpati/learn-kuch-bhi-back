"""Flashcards service class and simple module entrypoint.

Provides a high-level class for generating validated flashcard sets that can be
used in API handlers or background jobs. Mirrors the pattern from the video
generator for a consistent developer experience.
"""

from __future__ import annotations

from typing import Optional

from app.modules.flashcards.generator import (
    generate_flashcards,
    generate_flashcards_sync,
    generate_outline,
)
from app.modules.flashcards.models.flashcards import FlashcardSet
from app.modules.flashcards.models.outline import (
    MultiFlashcardsResult,
    SubtopicFlashcards,
)


class FlashcardsGenerator:
    """High-level service for generating flashcard sets.

    Example (async):
        svc = FlashcardsGenerator()
        fc = await svc.generate("Basics of Linear Algebra")

    Example (sync):
        svc = FlashcardsGenerator()
        fc = svc.generate_sync("Photosynthesis for 8th graders")
    """

    def __init__(self) -> None:
        pass

    async def generate(self, prompt: str) -> FlashcardSet:
        """Generate a flashcard set asynchronously."""
        return await generate_flashcards(prompt)

    def generate_sync(self, prompt: str) -> FlashcardSet:
        """Synchronous wrapper for convenience and scripting."""

        return generate_flashcards_sync(prompt)

    @staticmethod
    def to_jsonable(flashcards: FlashcardSet) -> dict:
        """Convert a FlashcardSet into a JSON-serializable dict."""
        return flashcards.model_dump()


class MultiFlashcardsGenerator:
    """Orchestrates an outline agent and per-subtopic flashcard agents."""

    def __init__(self, *, concurrency: int = 6) -> None:
        self.concurrency = max(1, int(concurrency))

    async def generate(
        self,
        base_prompt: str,
    ) -> MultiFlashcardsResult:
        outline = await generate_outline(base_prompt)

        # Build tasks for subtopics
        import asyncio

        sem = asyncio.Semaphore(self.concurrency)
        results: list[SubtopicFlashcards] = []

        async def _one(topic_name: str, subtopic_name: str) -> None:
            async with sem:
                prompt = (
                    f"Generate a sensible, study-friendly number of high-quality flashcards for "
                    f"the subtopic '{subtopic_name}' under the topic '{topic_name}'. "
                    f"Overall subject: {base_prompt}. "
                    "Audience: undergrad-friendly, precise. "
                    "No markdown; plain text questions and answers."
                )
                fc = await generate_flashcards(prompt)
                results.append(
                    SubtopicFlashcards(
                        topic=topic_name, subtopic=subtopic_name, flashcard_set=fc
                    )
                )

        tasks: list[asyncio.Task] = []
        for t in outline.topics or []:
            for s in t.subtopics or []:
                tasks.append(asyncio.create_task(_one(t.name, s.name)))

        if tasks:
            await asyncio.gather(*tasks)

        return MultiFlashcardsResult(outline=outline, sets=results)

    def generate_sync(
        self,
        base_prompt: str,
    ) -> MultiFlashcardsResult:
        import asyncio

        return asyncio.run(self.generate(base_prompt))


def main(prompt: Optional[str] = None) -> int:
    """Ad-hoc entry: generate once and print JSON to stdout.

    Not wired to a console script by default; useful for quick local testing.
    """
    import json

    if not prompt:
        print("Provide a prompt argument to generate flashcards.")
        return 2
    svc = FlashcardsGenerator()

    fc = svc.generate_sync(prompt)
    print(json.dumps(fc.model_dump(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    import sys

    arg = sys.argv[1] if len(sys.argv) > 1 else None
    raise SystemExit(main(arg))
