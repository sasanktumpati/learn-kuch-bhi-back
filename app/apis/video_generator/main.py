from __future__ import annotations

from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse
import asyncio
import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.db.base import get_session, async_session_maker
from app.core.db.schemas.auth import User
from app.core.db.schemas.videos import (
    VideoGenerationRequest as DBRequest,
    VideoGenerationResult as DBResult,
    GenerationStatus as DBStatus,
)
from app.modules.auth import fastapi_users
from app.apis.deps import current_user_or_query_token
from app.modules.video_generator.main import VideoGenerator
from app.core.db_services import VideoGenerationService
from app.core.task_queue import enqueue_video_generation
import uuid as _uuid
from .schemas import (
    GenerateVideoRequest,
    GenerateVideoResponse,
    PipelineSummary,
    RequestStatusResponse,
    VideoRead,
    RequestRead,
)


router = APIRouter()

CurrentUser = Annotated[User, Depends(fastapi_users.current_user())]


@router.post(
    f"/{settings.app.version}/videos/generate",
    response_model=GenerateVideoResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["videos"],
)
async def generate_video(
    req: GenerateVideoRequest,
    user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> GenerateVideoResponse:
    """Enqueue a Manim video generation request and return queued status."""
    video_uuid = str(_uuid.uuid4())

    db = VideoGenerationService(session)
    request = await db.create_generation_request(
        user_id=user.id,
        video_id=video_uuid,
        prompt=req.prompt,
        scene_file=req.scene_file,
        scene_name=req.scene_name,
        extra_packages=req.extra_packages,
        max_lint_batch_rounds=req.max_lint_batch_rounds,
        max_post_runtime_lint_rounds=req.max_post_runtime_lint_rounds,
        max_runtime_fix_attempts=req.max_runtime_fix_attempts,
    )

    # Enqueue background work using the created request
    enqueue_video_generation(
        request_id=request.id,
        user_id=user.id,
        title=req.title,
        description=req.description,
    )

    # Respond with a queued/pending summary
    summary = PipelineSummary(
        ok=False,
        video_path=None,
        lint_issues=[],
        runtime_errors=[],
    )
    status_url = f"/{settings.app.version}/videos/requests/{video_uuid}"
    return GenerateVideoResponse(
        request_id=request.id,
        video_uuid=video_uuid,
        video_id=None,
        status=request.status.value,
        pipeline=summary,
        status_url=status_url,
    )


@router.get(
    f"/{settings.app.version}/videos/requests/{{video_uuid}}",
    response_model=RequestStatusResponse,
    tags=["videos"],
)
async def request_status(
    video_uuid: str,
    user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> RequestStatusResponse:
    from app.core.db_services import VideoGenerationService

    db = VideoGenerationService(session)
    req = await db.get_request_by_video_id(video_uuid)
    if not req or req.user_id != user.id:
        # Hide existence if it doesn't belong to the user
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Request not found")

    def ts(d: Optional[datetime]) -> Optional[str]:
        return d.isoformat() if d else None

    # Load result if present
    res_row = await session.execute(
        select(DBResult).where(DBResult.request_id == req.id)
    )
    res = res_row.scalar_one_or_none()

    return RequestStatusResponse(
        request_id=req.id,
        video_uuid=req.video_id,
        status=req.status.value,
        started_at=ts(req.started_at),
        completed_at=ts(req.completed_at),
        result_id=res.id if res else None,
        video_id=res.video_id if res else None,
        error_message=(res.error_message if res else None),
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
    f"/{settings.app.version}/videos/requests/{{video_uuid}}/events",
    tags=["videos"],
)
async def request_events(
    video_uuid: str,
    user: User = Depends(current_user_or_query_token),
) -> StreamingResponse:
    from app.core.db_services import VideoGenerationService

    # Validate ownership with a short-lived session
    async with async_session_maker() as _sess:
        db = VideoGenerationService(_sess)
        req = await db.get_request_by_video_id(video_uuid)
        if not req or req.user_id != user.id:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="Request not found")

    async def gen():
        last_status = None
        tick = 0
        try:
            while True:
                # Use a new session for each iteration to avoid connection leaks
                async with async_session_maker() as session:
                    db = VideoGenerationService(session)
                    r = await db.get_request_by_video_id(video_uuid)
                    if not r:
                        yield _sse("end", {"reason": "deleted"})
                        break
                    if r.status.value != last_status:
                        last_status = r.status.value
                        payload = {
                            "status": last_status,
                            "request_id": r.id,
                            "video_uuid": r.video_id,
                            "started_at": r.started_at.isoformat()
                            if r.started_at
                            else None,
                            "completed_at": r.completed_at.isoformat()
                            if r.completed_at
                            else None,
                        }
                        yield _sse("status", payload)

                    if last_status in ("completed", "failed"):
                        yield _sse("end", {"status": last_status})
                        break
                # Session is now properly closed after each iteration

                # Heartbeat ping every 15 seconds
                tick += 1
                if tick % 15 == 0:
                    from datetime import datetime as _dt

                    yield _sse("ping", {"ts": _dt.utcnow().isoformat() + "Z"})

                await asyncio.sleep(1)
        except asyncio.CancelledError:
            # Client disconnected - session already closed by context manager
            return

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.get(
    f"/{settings.app.version}/videos",
    response_model=list[VideoRead],
    tags=["videos"],
)
async def list_videos(
    user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> list[VideoRead]:
    from sqlalchemy import select
    from app.core.db.schemas.videos import Videos as DBVideo

    rows = await session.execute(
        select(DBVideo)
        .where(DBVideo.user_id == user.id)
        .order_by(DBVideo.uploaded_at.desc())
    )
    videos = rows.scalars().all()
    out: list[VideoRead] = []
    for v in videos:
        out.append(
            VideoRead(
                id=v.id,
                title=v.title,
                description=v.description,
                path=v.path,
                original_path=v.original_path,
                file_size=v.file_size,
                duration=v.duration,
                uploaded_at=v.uploaded_at.isoformat(),
            )
        )
    return out


@router.get(
    f"/{settings.app.version}/videos/{{video_id:int}}",
    response_model=VideoRead,
    tags=["videos"],
)
async def get_video(
    video_id: int,
    user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> VideoRead:
    from sqlalchemy import select
    from fastapi import HTTPException
    from app.core.db.schemas.videos import Videos as DBVideo

    row = await session.execute(
        select(DBVideo).where(DBVideo.id == video_id, DBVideo.user_id == user.id)
    )
    v = row.scalar_one_or_none()
    if not v:
        raise HTTPException(status_code=404, detail="Video not found")
    return VideoRead(
        id=v.id,
        title=v.title,
        description=v.description,
        path=v.path,
        original_path=v.original_path,
        file_size=v.file_size,
        duration=v.duration,
        uploaded_at=v.uploaded_at.isoformat(),
    )


@router.get(
    f"/{settings.app.version}/videos/requests",
    response_model=list[RequestRead],
    tags=["videos"],
)
async def list_requests(
    user: CurrentUser,
    session: AsyncSession = Depends(get_session),
) -> list[RequestRead]:
    from sqlalchemy import select
    from app.core.db.schemas.videos import VideoGenerationRequest as DBRequest

    rows = await session.execute(
        select(DBRequest)
        .where(DBRequest.user_id == user.id)
        .order_by(DBRequest.created_at.desc())
    )
    reqs = rows.scalars().all()
    out: list[RequestRead] = []
    for r in reqs:
        out.append(
            RequestRead(
                id=r.id,
                video_uuid=r.video_id,
                status=r.status.value,
                created_at=r.created_at.isoformat(),
                started_at=r.started_at.isoformat() if r.started_at else None,
                completed_at=r.completed_at.isoformat() if r.completed_at else None,
            )
        )
    return out
