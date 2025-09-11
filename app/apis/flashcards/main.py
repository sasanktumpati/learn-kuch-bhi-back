from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse
import asyncio
import json
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db.base import get_session, async_session_maker
from app.core.db.schemas.auth import User
from app.core.db.schemas.flashcards import (
    MultiFlashcardsResult as DBMulti,
    FlashcardSet as DBSet,
)
from app.modules.auth import fastapi_users
from app.apis.deps import current_user_or_query_token
from app.modules.flashcards.main import MultiFlashcardsGenerator
from app.modules.flashcards.generator import generate_outline as _generate_outline
from app.core.db_services import FlashcardGenerationService
from app.core.task_queue import enqueue_flashcards_generation
from app.modules.flashcards.models.outline import TopicOutline
from .schemas import (
    OutlineRequest,
    OutlineResponse,
    GeneratePersistRequest,
    GeneratePersistResponse,
    MultiRunSummary,
    FlashcardSetSummary,
    FlashcardRead,
    FlashcardSetRead,
    AggregatedFlashcardsResponse,
)


router = APIRouter()

CurrentUser = Annotated[User, Depends(fastapi_users.current_user())]


@router.post(
    f"/{settings.app.version}/flashcards/outline",
    response_model=OutlineResponse,
    status_code=status.HTTP_200_OK,
    tags=["flashcards"],
)
async def create_outline(req: OutlineRequest) -> OutlineResponse:
    outline: TopicOutline = await _generate_outline(req.base_prompt)
    return OutlineResponse(outline=outline)


@router.post(
    f"/{settings.app.version}/flashcards/generate",
    response_model=GeneratePersistResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["flashcards"],
)
async def generate_and_persist(
    req: GeneratePersistRequest,
    user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> GeneratePersistResponse:
    # Create a pending multi-run record and enqueue background job
    db = FlashcardGenerationService(session)
    pending = await db.create_multi_result_pending(
        user_id=user.id,
        original_prompt=req.base_prompt,
        concurrency_setting=4,
    )

    enqueue_flashcards_generation(
        multi_result_id=pending.id,
        user_id=user.id,
        base_prompt=req.base_prompt,
        concurrency=4,
    )

    summary = MultiRunSummary(
        id=pending.id,
        status=pending.status.value,
        outline=pending.outline,
        created_at=pending.created_at.isoformat() if pending.created_at else None,
        completed_at=None,
        sets_created=0,
    )
    base = f"/{settings.app.version}/flashcards/runs/{pending.id}"
    return GeneratePersistResponse(
        run=summary,
        status_url=base,
        sets_url=f"{base}/sets",
    )


@router.get(
    f"/{settings.app.version}/flashcards/sets",
    response_model=list[FlashcardSetSummary],
    tags=["flashcards"],
)
async def list_flashcard_sets(
    user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> list[FlashcardSetSummary]:
    from sqlalchemy import select
    rows = await session.execute(
        select(DBSet).where(DBSet.user_id == user.id).order_by(DBSet.created_at.desc())
    )
    sets = rows.scalars().all()
    return [
        FlashcardSetSummary(
            id=s.id,
            title=s.title,
            description=s.description,
            tags=s.tags or [],
            status=s.status.value,
            created_at=s.created_at.isoformat(),
        )
        for s in sets
    ]


@router.get(
    f"/{settings.app.version}/flashcards/sets/{{set_id:int}}",
    response_model=FlashcardSetRead,
    tags=["flashcards"],
)
async def get_flashcard_set(
    set_id: int,
    user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> FlashcardSetRead:
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from fastapi import HTTPException
    result = await session.execute(
        select(DBSet)
        .options(selectinload(DBSet.flashcards))
        .where(DBSet.id == set_id, DBSet.user_id == user.id)
    )
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Flashcard set not found")
    return FlashcardSetRead(
        id=s.id,
        title=s.title,
        description=s.description,
        tags=s.tags or [],
        status=s.status.value,
        created_at=s.created_at.isoformat(),
        flashcards=[FlashcardRead(id=c.id, question=c.question, answer=c.answer, order_index=c.order_index) for c in (s.flashcards or [])],
    )


@router.get(
    f"/{settings.app.version}/flashcards/runs",
    response_model=list[MultiRunSummary],
    tags=["flashcards"],
)
async def list_flashcard_runs(
    user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> list[MultiRunSummary]:
    from sqlalchemy import select
    from app.core.db.schemas.flashcards import MultiFlashcardsResult as DBMulti

    rows = await session.execute(
        select(DBMulti).where(DBMulti.user_id == user.id).order_by(DBMulti.created_at.desc())
    )
    runs = rows.scalars().all()

    out: list[MultiRunSummary] = []
    for r in runs:
        sets_q = await session.execute(select(DBSet).where(DBSet.multi_result_id == r.id))
        sets_count = len(sets_q.scalars().all())
        out.append(
            MultiRunSummary(
                id=r.id,
                status=r.status.value,
                outline=r.outline,
                created_at=r.created_at.isoformat() if r.created_at else None,
                completed_at=r.completed_at.isoformat() if r.completed_at else None,
                sets_created=sets_count,
            )
        )
    return out


@router.get(
    f"/{settings.app.version}/flashcards/runs/{{run_id:int}}",
    response_model=MultiRunSummary,
    tags=["flashcards"],
)
async def get_flashcard_run(
    run_id: int,
    user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> MultiRunSummary:
    from sqlalchemy import select
    from fastapi import HTTPException
    from app.core.db.schemas.flashcards import MultiFlashcardsResult as DBMulti

    row = await session.execute(
        select(DBMulti).where(DBMulti.id == run_id, DBMulti.user_id == user.id)
    )
    r = row.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Run not found")
    sets_q = await session.execute(select(DBSet).where(DBSet.multi_result_id == r.id))
    sets_count = len(sets_q.scalars().all())
    return MultiRunSummary(
        id=r.id,
        status=r.status.value,
        outline=r.outline,
        created_at=r.created_at.isoformat() if r.created_at else None,
        completed_at=r.completed_at.isoformat() if r.completed_at else None,
        sets_created=sets_count,
    )


@router.get(
    f"/{settings.app.version}/flashcards/runs/{{run_id:int}}/sets",
    response_model=list[FlashcardSetSummary],
    tags=["flashcards"],
)
async def list_run_sets(
    run_id: int,
    user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> list[FlashcardSetSummary]:
    from sqlalchemy import select
    from fastapi import HTTPException
    from app.core.db.schemas.flashcards import MultiFlashcardsResult as DBMulti

    # Ensure run belongs to user
    row = await session.execute(
        select(DBMulti).where(DBMulti.id == run_id, DBMulti.user_id == user.id)
    )
    if not row.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Run not found")

    rows = await session.execute(
        select(DBSet).where(DBSet.multi_result_id == run_id).order_by(DBSet.created_at.desc())
    )
    sets = rows.scalars().all()
    return [
        FlashcardSetSummary(
            id=s.id,
            title=s.title,
            description=s.description,
            tags=s.tags or [],
            status=s.status.value,
            created_at=s.created_at.isoformat(),
        )
        for s in sets
    ]


@router.get(
    f"/{settings.app.version}/flashcards/runs/{{run_id:int}}/all-flashcards",
    response_model=AggregatedFlashcardsResponse,
    tags=["flashcards"],
)
async def get_all_flashcards_for_run(
    run_id: int,
    user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> AggregatedFlashcardsResponse:
    """Get all flashcards for a specific run in one aggregated response."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from fastapi import HTTPException

    # Get the specific multi-result run
    result = await session.execute(
        select(DBMulti)
        .where(DBMulti.id == run_id, DBMulti.user_id == user.id)
        .options(
            selectinload(DBMulti.flashcard_sets).selectinload(DBSet.flashcards)
        )
    )
    run = result.scalar_one_or_none()

    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    all_sets = []
    total_flashcards = 0

    for flashcard_set in run.flashcard_sets or []:
        flashcards = [
            FlashcardRead(
                id=c.id,
                question=c.question,
                answer=c.answer,
                order_index=c.order_index
            )
            for c in (flashcard_set.flashcards or [])
        ]
        total_flashcards += len(flashcards)

        set_read = FlashcardSetRead(
            id=flashcard_set.id,
            title=flashcard_set.title,
            description=flashcard_set.description,
            tags=flashcard_set.tags or [],
            status=flashcard_set.status.value,
            created_at=flashcard_set.created_at.isoformat(),
            flashcards=flashcards,
        )
        all_sets.append(set_read)

    return AggregatedFlashcardsResponse(
        prompt=run.original_prompt or "",
        total_sets=len(all_sets),
        total_flashcards=total_flashcards,
        sets=all_sets,
    )


def _sse(event: str | None, data: dict) -> bytes:
    payload = json.dumps(data, ensure_ascii=False)
    parts = []
    if event:
        parts.append(f"event: {event}")
    parts.append(f"data: {payload}")
    parts.append("")
    return ("\n".join(parts) + "\n").encode("utf-8")


@router.get(
    f"/{settings.app.version}/flashcards/runs/{{run_id:int}}/events",
    tags=["flashcards"],
)
async def stream_run_events(
    run_id: int,
    user: User = Depends(current_user_or_query_token),
) -> StreamingResponse:
    from sqlalchemy import select
    from app.core.db.schemas.flashcards import (
        MultiFlashcardsResult as DBMulti,
        GenerationStatus as FCStatus,
    )

    # Validate ownership using a short-lived session
    async with async_session_maker() as _sess:
        row = await _sess.execute(
            select(DBMulti).where(DBMulti.id == run_id, DBMulti.user_id == user.id)
        )
        run = row.scalar_one_or_none()
        if not run:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="Run not found")

    async def gen():
        last_status = None
        seen_ids: set[int] = set()
        tick = 0
        try:
            async with async_session_maker() as session:
                while True:
                    # Reload status and sets
                    row = await session.execute(
                        select(DBMulti).where(DBMulti.id == run_id)
                    )
                    r = row.scalar_one_or_none()
                    if not r:
                        yield _sse("end", {"reason": "deleted"})
                        break

                    if r.status.value != last_status:
                        last_status = r.status.value
                        # Compute partial counts
                        outline = r.outline or {}
                        topics = (
                            outline.get("topics", []) if isinstance(outline, dict) else []
                        )
                        total_expected = sum(
                            len(t.get("subtopics", []) or []) for t in topics
                        )

                        rows_all = await session.execute(
                            select(DBSet).where(DBSet.multi_result_id == run_id)
                        )
                        sets_all = rows_all.scalars().all()
                        sets_created = len(sets_all)

                        rows_completed = [
                            s
                            for s in sets_all
                            if getattr(s.status, "value", str(s.status))
                            == FCStatus.COMPLETED.value
                        ]
                        sets_completed = len(rows_completed)

                        # progress percent if we know total_expected
                        progress_percent = None
                        if total_expected and total_expected > 0:
                            progress_percent = round(
                                (sets_completed / total_expected) * 100.0, 2
                            )

                        yield _sse(
                            "status",
                            {
                                "status": last_status,
                                "sets_created": sets_created,
                                "sets_completed": sets_completed,
                                "total_expected": total_expected or None,
                                "progress_percent": progress_percent,
                            },
                        )

                    rows = await session.execute(
                        select(DBSet).where(DBSet.multi_result_id == run_id)
                    )
                    for s in rows.scalars().all():
                        if s.id in seen_ids:
                            continue
                        seen_ids.add(s.id)
                        yield _sse(
                            "set",
                            {
                                "id": s.id,
                                "title": s.title,
                                "description": s.description,
                                "tags": s.tags or [],
                                "status": s.status.value,
                                "created_at": s.created_at.isoformat(),
                            },
                        )

                    if last_status in ("completed", "failed"):
                        yield _sse("end", {"status": last_status})
                        break

                    # Heartbeat ping every 15 seconds
                    tick += 1
                    if tick % 15 == 0:
                        try:
                            ts = datetime.utcnow().isoformat() + "Z"
                        except Exception:
                            ts = None
                        yield _sse("ping", {"ts": ts})

                    await asyncio.sleep(1)
        except asyncio.CancelledError:
            # Client disconnected
            return

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
