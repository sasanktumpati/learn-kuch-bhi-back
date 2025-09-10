from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.base import async_session_maker
from app.core.db_services import VideoGenerationService
from app.core.db_services import FlashcardGenerationService
from app.modules.video_generator.main import VideoGenerator
from app.core.db.schemas.videos import GenerationStatus as VideoStatus
from app.core.db.schemas.flashcards import GenerationStatus as FCStatus
from app.modules.flashcards.generator import (
    generate_outline as fc_generate_outline,
    generate_flashcards as fc_generate_flashcards,
)


JobCallable = Callable[[], Awaitable[None]]


class BackgroundQueue:
    """Simple in-process async job queue with fixed concurrency."""

    def __init__(self, *, concurrency: int = 2) -> None:
        self.concurrency = max(1, int(concurrency))
        self._queue: asyncio.Queue[JobCallable] = asyncio.Queue()
        self._workers: list[asyncio.Task[None]] = []
        self._started = False

    async def _worker(self, idx: int) -> None:
        while True:
            job = await self._queue.get()
            try:
                await job()
            except Exception as e:  # noqa: BLE001
                # Best-effort logging; avoid crashing the worker
                print(f"[queue] Worker {idx} job failed: {e}")
            finally:
                self._queue.task_done()

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        for i in range(self.concurrency):
            self._workers.append(asyncio.create_task(self._worker(i)))

    async def stop(self) -> None:
        # Drain queue and cancel workers
        await self._queue.join()
        for t in self._workers:
            t.cancel()
        self._workers.clear()
        self._started = False

    def enqueue(self, fn: JobCallable) -> None:
        self._queue.put_nowait(fn)


queue = BackgroundQueue(concurrency=2)


def enqueue_video_generation(
    *,
    request_id: int,
    user_id: int,
    title: str,
    description: str,
) -> None:
    """Enqueue a job that processes an existing VideoGenerationRequest."""

    async def _job() -> None:
        async with async_session_maker() as session:  # type: AsyncSession
            db = VideoGenerationService(session)

            # Mark processing
            from datetime import datetime

            await db.update_request_status(
                request_id, VideoStatus.PROCESSING, started_at=datetime.now()
            )

            # Load the request row for parameters
            from sqlalchemy import select
            from app.core.db.schemas.videos import VideoGenerationRequest as DBRequest

            row = await session.execute(select(DBRequest).where(DBRequest.id == request_id))
            db_req = row.scalar_one_or_none()
            if not db_req:
                print(f"[queue] Request id {request_id} not found")
                return

            vg = VideoGenerator()
            # Run pipeline without creating a new request. Save under existing request.
            result = await vg.generate(
                prompt=db_req.original_prompt,
                video_id=db_req.video_id,
                scene_file=db_req.scene_file,
                scene_name=db_req.scene_name,
                extra_packages=db_req.extra_packages,
                max_lint_batch_rounds=db_req.max_lint_batch_rounds,
                max_post_runtime_lint_rounds=db_req.max_post_runtime_lint_rounds,
                max_runtime_fix_attempts=db_req.max_runtime_fix_attempts,
            )

            # Persist results
            generation_result, video_record = await db.save_generation_result(
                request_id=db_req.id,
                pipeline_result=result,
                user_id=user_id,
                title=title,
                description=description,
            )

            from datetime import datetime

            final_status = VideoStatus.COMPLETED if result.ok else VideoStatus.FAILED
            await db.update_request_status(
                db_req.id, final_status, completed_at=datetime.now()
            )

    queue.enqueue(_job)


def enqueue_flashcards_generation(
    *,
    multi_result_id: int,
    user_id: int,
    base_prompt: str,
    concurrency: int = 6,
) -> None:
    """Enqueue a job that processes a MultiFlashcardsResult from PENDING -> COMPLETED."""

    async def _job() -> None:
        async with async_session_maker() as session:
            db = FlashcardGenerationService(session)

            # Load the run row
            from sqlalchemy import select
            from app.core.db.schemas.flashcards import MultiFlashcardsResult as DBMulti

            res = await session.execute(
                select(DBMulti).where(DBMulti.id == multi_result_id)
            )
            db_run = res.scalar_one_or_none()
            if not db_run:
                print(f"[queue] Flashcards run id {multi_result_id} not found")
                return

            # Update to processing
            await db.update_multi_result_status(multi_result_id, FCStatus.PROCESSING)

            # Generate outline and persist
            outline = await fc_generate_outline(base_prompt)
            db_run.outline = outline.model_dump()
            await session.commit()

            # Create topics/subtopics
            index = await db.create_topics_and_subtopics(
                multi_result_id=db_run.id, outline=outline
            )

            # Generate per subtopic and persist
            from datetime import datetime

            for t in outline.topics or []:
                for s in t.subtopics or []:
                    sub_id = index.get((t.name, s.name))
                    if not sub_id:
                        continue
                    placeholder = await db.create_placeholder_flashcard_set(
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
                    fc = await fc_generate_flashcards(prompt)
                    await db.finalize_flashcard_set(set_id=placeholder.id, pydantic_set=fc)

            await db.update_multi_result_status(
                db_run.id, FCStatus.COMPLETED, completed_at=datetime.now()
            )

    queue.enqueue(_job)
