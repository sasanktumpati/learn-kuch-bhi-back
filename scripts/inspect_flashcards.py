"""Quick DB inspector for flashcards data.

Runs lightweight queries to summarize flashcard sets, counts, and a few
examples to inform schema cleanup/migration planning.

Usage:
  uv run scripts/inspect_flashcards.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Ensure project root is on sys.path so `app` package imports resolve
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.core.db import get_session
from app.core.db.schemas.flashcards import (
    FlashcardSet,
    Flashcard,
    MultiFlashcardsResult,
    Topic,
)


async def main() -> int:
    async for session in get_session():  # get_session is an async generator
        # Counts
        total_sets = (
            await session.execute(select(func.count(FlashcardSet.id)))
        ).scalar() or 0
        total_cards = (
            await session.execute(select(func.count(Flashcard.id)))
        ).scalar() or 0

        print("Flashcards DB summary:")
        print(f"- Flashcard sets: {total_sets}")
        print(f"- Flashcards: {total_cards}")

        # Show 5 most recent sets with tag info and card counts
        recent_q = (
            select(FlashcardSet)
            .options(selectinload(FlashcardSet.flashcards))
            .order_by(FlashcardSet.created_at.desc())
            .limit(5)
        )
        recent_sets = (await session.execute(recent_q)).scalars().all()

        if not recent_sets:
            print("- No flashcard sets found.")
            return 0

        print("\nRecent sets:")
        for s in recent_sets:
            tags = s.tags if isinstance(s.tags, list) else []
            print(
                f"  • ID {s.id} | title={s.title!r} | tags={tags} | "
                f"cards={len(s.flashcards)} | status={getattr(s, 'status', None)}"
            )

        # Sample a set with its first 3 cards
        print("\nSample cards (first recent set):")
        first = recent_sets[0]
        for c in first.flashcards[:3]:
            print(f"  - Q: {c.question[:100]!r}")
            print(f"    A: {c.answer[:120]!r}")

        # Show linkage of recent multi runs
        print("\nRecent multi generation runs:")
        runs = (
            (
                await session.execute(
                    select(MultiFlashcardsResult)
                    .options(
                        selectinload(MultiFlashcardsResult.flashcard_sets),
                        selectinload(MultiFlashcardsResult.topics).selectinload(
                            Topic.subtopics
                        ),
                    )
                    .order_by(MultiFlashcardsResult.created_at.desc())
                    .limit(3)
                )
            )
            .scalars()
            .all()
        )
        if not runs:
            print("- No multi runs found.")
        for r in runs:
            subtopics = sum(len(t.subtopics) for t in r.topics)
            print(
                f"  • Run {r.id} status={r.status} topics={len(r.topics)} subtopics={subtopics} sets_linked={len(r.flashcard_sets)}"
            )

        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
