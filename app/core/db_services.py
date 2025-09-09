"""Database service classes for video and flashcard generation operations."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.db.schemas.videos import (
    VideoGenerationRequest,
    VideoGenerationResult,
    Videos,
    GenerationStatus as VideoGenerationStatus,
)
from app.core.db.schemas.flashcards import (
    FlashcardSet,
    Flashcard,
    MultiFlashcardsResult,
    Topic,
    GenerationStatus as FlashcardGenerationStatus,
)
from app.modules.flashcards.models.flashcards import (
    FlashcardSet as PydanticFlashcardSet,
)
from app.modules.flashcards.models.outline import (
    MultiFlashcardsResult as PydanticMultiFlashcardsResult,
    TopicOutline as PydanticTopicOutline,
)
from app.modules.video_generator.pipeline import PipelineResult
from app.core.video_manager import video_manager


class VideoGenerationService:
    """Service for managing video generation requests and results in the database."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_generation_request(
        self,
        user_id: int,
        video_id: str,
        prompt: str,
        scene_file: str = "scene.py",
        scene_name: str = "GeneratedScene",
        extra_packages: Optional[list[str]] = None,
        max_lint_batch_rounds: int = 2,
        max_post_runtime_lint_rounds: int = 2,
        max_runtime_fix_attempts: int = 2,
    ) -> VideoGenerationRequest:
        """Create a new video generation request."""
        request = VideoGenerationRequest(
            user_id=user_id,
            video_id=video_id,
            original_prompt=prompt,
            scene_file=scene_file,
            scene_name=scene_name,
            extra_packages=extra_packages or [],
            max_lint_batch_rounds=max_lint_batch_rounds,
            max_post_runtime_lint_rounds=max_post_runtime_lint_rounds,
            max_runtime_fix_attempts=max_runtime_fix_attempts,
            status=VideoGenerationStatus.PENDING,
        )

        self.session.add(request)
        await self.session.commit()
        await self.session.refresh(request)
        return request

    async def update_request_status(
        self,
        request_id: int,
        status: VideoGenerationStatus,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
    ) -> None:
        """Update the status of a generation request."""
        result = await self.session.execute(
            select(VideoGenerationRequest).where(
                VideoGenerationRequest.id == request_id
            )
        )
        request = result.scalar_one_or_none()

        if request:
            request.status = status
            if started_at:
                request.started_at = started_at
            if completed_at:
                request.completed_at = completed_at
            await self.session.commit()

    async def save_generation_result(
        self,
        request_id: int,
        pipeline_result: "PipelineResult",
        user_id: int,
        title: str,
        description: str = "",
    ) -> tuple[VideoGenerationResult, Optional[Videos]]:
        """Save the pipeline result and optionally create a Videos record."""

        generation_result = VideoGenerationResult(
            request_id=request_id,
            success=pipeline_result.ok,
            video_path=pipeline_result.video_path,
            upgraded_prompt=pipeline_result.upgraded.model_dump()
            if pipeline_result.upgraded
            else None,
            generated_code=pipeline_result.code,
            lint_issues=[issue.model_dump() for issue in pipeline_result.lint_issues],
            runtime_errors=pipeline_result.runtime_errors,
            logs=pipeline_result.logs,
            error_message=None if pipeline_result.ok else "Generation failed",
        )

        video_record = None

        if pipeline_result.ok and pipeline_result.video_path:
            try:
                serving_path, metadata = video_manager.move_video_to_serving(
                    pipeline_result.video_path, user_id, title
                )

                video_record = Videos(
                    user_id=user_id,
                    title=title,
                    description=description
                    or f"Generated video from prompt: {title[:100]}...",
                    path=str(serving_path),
                    original_path=pipeline_result.video_path,
                    file_size=metadata.get("file_size"),
                    duration=metadata.get("duration"),
                )

                self.session.add(video_record)
                await self.session.flush()

                generation_result.video_id = video_record.id

            except Exception as e:
                generation_result.error_message = f"Video processing failed: {str(e)}"

        self.session.add(generation_result)
        await self.session.commit()

        if video_record:
            await self.session.refresh(video_record)
        await self.session.refresh(generation_result)

        return generation_result, video_record

    async def get_request_by_video_id(
        self, video_id: str
    ) -> Optional[VideoGenerationRequest]:
        """Get generation request by video ID."""
        result = await self.session.execute(
            select(VideoGenerationRequest).where(
                VideoGenerationRequest.video_id == video_id
            )
        )
        return result.scalar_one_or_none()


class FlashcardGenerationService:
    """Service for managing flashcard generation and storage in the database."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_multi_result_processing(
        self,
        *,
        user_id: int,
        outline_json: dict,
        original_prompt: str,
        concurrency_setting: int = 6,
    ) -> MultiFlashcardsResult:
        """Create a multi generation record with PROCESSING status."""
        db_multi = MultiFlashcardsResult(
            user_id=user_id,
            outline=outline_json,
            original_prompt=original_prompt,
            concurrency_setting=concurrency_setting,
            status=FlashcardGenerationStatus.PROCESSING,
        )
        self.session.add(db_multi)
        await self.session.commit()
        await self.session.refresh(db_multi)
        return db_multi

    async def create_topics_and_subtopics(
        self,
        *,
        multi_result_id: int,
        outline: "PydanticTopicOutline",
    ) -> dict[tuple[str, str], int]:
        """Create Topic/Subtopic rows from outline; return mapping to subtopic IDs."""
        from app.core.db.schemas.flashcards import (
            Topic as DBTopic,
            Subtopic as DBSubtopic,
        )

        index: dict[tuple[str, str], int] = {}
        for t_idx, t in enumerate(outline.topics or []):
            db_topic = DBTopic(
                multi_result_id=multi_result_id,
                name=t.name,
                description=getattr(t, "description", None),
                order_index=t_idx,
            )
            self.session.add(db_topic)
            await self.session.flush()

            for s_idx, s in enumerate(t.subtopics or []):
                db_sub = DBSubtopic(
                    topic_id=db_topic.id,
                    name=s.name,
                    description=getattr(s, "description", None),
                    order_index=s_idx,
                )
                self.session.add(db_sub)
                await self.session.flush()
                index[(t.name, s.name)] = db_sub.id

        await self.session.commit()
        return index

    async def create_placeholder_flashcard_set(
        self,
        *,
        user_id: int,
        multi_result_id: int,
        subtopic_id: int,
        original_prompt: str,
        title: str,
        description: str | None = None,
        tags: list[str] | None = None,
    ) -> FlashcardSet:
        """Create a placeholder set with PROCESSING status and no cards yet."""
        db_set = FlashcardSet(
            user_id=user_id,
            title=title,
            description=description or "Generating...",
            tags=tags or [],
            original_prompt=original_prompt,
            status=FlashcardGenerationStatus.PROCESSING,
            multi_result_id=multi_result_id,
            subtopic_id=subtopic_id,
        )
        self.session.add(db_set)
        await self.session.commit()
        await self.session.refresh(db_set)
        return db_set

    async def finalize_flashcard_set(
        self,
        *,
        set_id: int,
        pydantic_set: PydanticFlashcardSet,
    ) -> FlashcardSet:
        """Fill in metadata and add cards to an existing placeholder set."""
        result = await self.session.execute(
            select(FlashcardSet).where(FlashcardSet.id == set_id)
        )
        db_set = result.scalar_one()
        db_set.title = pydantic_set.title
        db_set.description = pydantic_set.description
        db_set.tags = pydantic_set.tags
        db_set.status = FlashcardGenerationStatus.COMPLETED
        await self.session.flush()

        for index, card in enumerate(pydantic_set.flashcards):
            self.session.add(
                Flashcard(
                    flashcard_set_id=db_set.id,
                    question=card.question,
                    answer=card.answer,
                    order_index=index,
                )
            )

        await self.session.commit()

        result = await self.session.execute(
            select(FlashcardSet)
            .options(selectinload(FlashcardSet.flashcards))
            .where(FlashcardSet.id == set_id)
        )
        return result.scalar_one()

    async def save_flashcard_set(
        self,
        user_id: int,
        pydantic_set: PydanticFlashcardSet,
        original_prompt: str,
        status: FlashcardGenerationStatus = FlashcardGenerationStatus.COMPLETED,
        *,
        multi_result_id: int | None = None,
        subtopic_id: int | None = None,
    ) -> FlashcardSet:
        """Save a Pydantic FlashcardSet to the database."""

        db_set = FlashcardSet(
            user_id=user_id,
            title=pydantic_set.title,
            description=pydantic_set.description,
            tags=pydantic_set.tags,
            original_prompt=original_prompt,
            status=status,
            multi_result_id=multi_result_id,
            subtopic_id=subtopic_id,
        )

        self.session.add(db_set)
        await self.session.flush()

        for index, card in enumerate(pydantic_set.flashcards):
            db_card = Flashcard(
                flashcard_set_id=db_set.id,
                question=card.question,
                answer=card.answer,
                order_index=index,
            )
            self.session.add(db_card)

        await self.session.commit()

        result = await self.session.execute(
            select(FlashcardSet)
            .options(selectinload(FlashcardSet.flashcards))
            .where(FlashcardSet.id == db_set.id)
        )
        return result.scalar_one()

    async def save_multi_flashcards_result(
        self,
        user_id: int,
        multi_result: PydanticMultiFlashcardsResult,
        original_prompt: str,
        concurrency_setting: int = 6,
    ) -> MultiFlashcardsResult:
        """Save a multi-flashcards result with proper relationship management."""
        db_multi_result = MultiFlashcardsResult(
            user_id=user_id,
            outline=multi_result.outline.model_dump(),
            original_prompt=original_prompt,
            concurrency_setting=concurrency_setting,
            status=FlashcardGenerationStatus.COMPLETED,
            completed_at=datetime.now(),
        )

        self.session.add(db_multi_result)
        await self.session.flush()

        subtopic_index: dict[tuple[str, str], int] = {}
        topics = multi_result.outline.topics or []
        for t_idx, t in enumerate(topics):
            res = await self.session.execute(
                select(MultiFlashcardsResult).where(
                    MultiFlashcardsResult.id == db_multi_result.id
                )
            )

            from app.core.db.schemas.flashcards import (
                Topic as DBTopic,
                Subtopic as DBSubtopic,
            )

            db_topic = DBTopic(
                multi_result_id=db_multi_result.id,
                name=t.name,
                description=None,
                order_index=t_idx,
            )
            self.session.add(db_topic)
            await self.session.flush()

            for s_idx, s in enumerate(t.subtopics or []):
                db_sub = DBSubtopic(
                    topic_id=db_topic.id,
                    name=s.name,
                    description=getattr(s, "description", None),
                    order_index=s_idx,
                )
                self.session.add(db_sub)
                await self.session.flush()
                subtopic_index[(t.name, s.name)] = db_sub.id

        for subtopic_set in multi_result.sets:
            sub_id = subtopic_index.get((subtopic_set.topic, subtopic_set.subtopic))
            _ = await self.save_flashcard_set(
                user_id=user_id,
                pydantic_set=subtopic_set.flashcard_set,
                original_prompt=f"{original_prompt} - {subtopic_set.topic}: {subtopic_set.subtopic}",
                multi_result_id=db_multi_result.id,
                subtopic_id=sub_id,
            )

        await self.session.commit()

        result = await self.session.execute(
            select(MultiFlashcardsResult)
            .options(
                selectinload(MultiFlashcardsResult.flashcard_sets),
                selectinload(MultiFlashcardsResult.topics).selectinload(
                    Topic.subtopics
                ),
            )
            .where(MultiFlashcardsResult.id == db_multi_result.id)
        )
        return result.scalar_one()

    async def update_multi_result_status(
        self,
        multi_result_id: int,
        status: FlashcardGenerationStatus,
        completed_at: Optional[datetime] = None,
    ) -> None:
        """Update the status of a multi-flashcards result."""
        result = await self.session.execute(
            select(MultiFlashcardsResult).where(
                MultiFlashcardsResult.id == multi_result_id
            )
        )
        multi_result = result.scalar_one_or_none()

        if multi_result:
            multi_result.status = status
            if completed_at:
                multi_result.completed_at = completed_at
            await self.session.commit()
