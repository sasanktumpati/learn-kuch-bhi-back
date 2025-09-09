"""Video generator service class and module entrypoint.

Provides a small, API-friendly wrapper class around the pipeline so your
endpoints or background jobs can call it directly. The module also remains
executable as a convenience entrypoint that delegates to the CLI.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from typing import Callable, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.video_generator.pipeline import PipelineResult, run_video_pipeline
from app.modules.video_generator.cli import main as _cli_main
from app.core.db_services import VideoGenerationService
from app.core.db.schemas.videos import GenerationStatus


class VideoGenerator:
    """High-level service for generating Manim videos.
    Example (async):
        svc = VideoGenerator()
        result = await svc.generate("Animate Pythagoras", video_id="vid-123")

    Example (sync):
        svc = VideoGenerator()
        result = svc.generate_sync("Animate Pythagoras")

    Example (with database):
        svc = VideoGenerator()
        result = await svc.generate_with_db(
            session, user_id=1, prompt="Animate Pythagoras",
            title="Pythagoras Animation"
        )
    """

    def __init__(self, *, uv_quiet: bool = False) -> None:
        self.uv_quiet = uv_quiet

    async def generate(
        self,
        prompt: str,
        *,
        video_id: Optional[str] = None,
        scene_file: str = "scene.py",
        scene_name: str = "GeneratedScene",
        extra_packages: list[str] | None = None,
        on_log: Optional[Callable[[str], None]] = None,
        max_lint_batch_rounds: int = 2,
        max_post_runtime_lint_rounds: int = 2,
        max_runtime_fix_attempts: int = 2,
    ) -> PipelineResult:
        """Run the end-to-end pipeline and return a detailed result."""
        vid = video_id or str(uuid.uuid4())
        return await run_video_pipeline(
            prompt,
            vid,
            scene_file=scene_file,
            scene_name=scene_name,
            extra_packages=extra_packages,
            on_log=on_log,
            uv_quiet=self.uv_quiet,
            max_lint_batch_rounds=max_lint_batch_rounds,
            max_post_runtime_lint_rounds=max_post_runtime_lint_rounds,
            max_runtime_fix_attempts=max_runtime_fix_attempts,
        )

    def generate_sync(
        self,
        prompt: str,
        *,
        video_id: Optional[str] = None,
        scene_file: str = "scene.py",
        scene_name: str = "GeneratedScene",
        extra_packages: list[str] | None = None,
        on_log: Optional[Callable[[str], None]] = None,
        max_lint_batch_rounds: int = 2,
        max_post_runtime_lint_rounds: int = 2,
        max_runtime_fix_attempts: int = 2,
    ) -> PipelineResult:
        """Synchronous wrapper for environments without an event loop."""
        return asyncio.run(
            self.generate(
                prompt,
                video_id=video_id,
                scene_file=scene_file,
                scene_name=scene_name,
                extra_packages=extra_packages,
                on_log=on_log,
                max_lint_batch_rounds=max_lint_batch_rounds,
                max_post_runtime_lint_rounds=max_post_runtime_lint_rounds,
                max_runtime_fix_attempts=max_runtime_fix_attempts,
            )
        )

    async def generate_with_db(
        self,
        session: AsyncSession,
        user_id: int,
        prompt: str,
        title: str,
        description: str = "",
        *,
        video_id: Optional[str] = None,
        scene_file: str = "scene.py",
        scene_name: str = "GeneratedScene",
        extra_packages: list[str] | None = None,
        on_log: Optional[Callable[[str], None]] = None,
        max_lint_batch_rounds: int = 2,
        max_post_runtime_lint_rounds: int = 2,
        max_runtime_fix_attempts: int = 2,
    ) -> tuple[PipelineResult, Optional[int]]:  # Returns (result, video_id_in_db)
        """Generate video and store all data in database with proper tracking."""
        vid = video_id or str(uuid.uuid4())

        # Create database service
        db_service = VideoGenerationService(session)

        # Create generation request record
        request = await db_service.create_generation_request(
            user_id=user_id,
            video_id=vid,
            prompt=prompt,
            scene_file=scene_file,
            scene_name=scene_name,
            extra_packages=extra_packages,
            max_lint_batch_rounds=max_lint_batch_rounds,
            max_post_runtime_lint_rounds=max_post_runtime_lint_rounds,
            max_runtime_fix_attempts=max_runtime_fix_attempts,
        )

        try:
            # Update status to processing
            await db_service.update_request_status(
                request.id, GenerationStatus.PROCESSING, started_at=datetime.now()
            )

            # Run the actual generation
            result = await self.generate(
                prompt,
                video_id=vid,
                scene_file=scene_file,
                scene_name=scene_name,
                extra_packages=extra_packages,
                on_log=on_log,
                max_lint_batch_rounds=max_lint_batch_rounds,
                max_post_runtime_lint_rounds=max_post_runtime_lint_rounds,
                max_runtime_fix_attempts=max_runtime_fix_attempts,
            )

            # Save the result to database
            generation_result, video_record = await db_service.save_generation_result(
                request.id, result, user_id, title, description
            )

            # Update final status
            final_status = (
                GenerationStatus.COMPLETED if result.ok else GenerationStatus.FAILED
            )
            await db_service.update_request_status(
                request.id, final_status, completed_at=datetime.now()
            )

            video_db_id = video_record.id if video_record else None
            return result, video_db_id

        except Exception:
            # Update status to failed on any exception
            await db_service.update_request_status(
                request.id, GenerationStatus.FAILED, completed_at=datetime.now()
            )
            raise

    @staticmethod
    def to_jsonable(result: PipelineResult) -> dict:
        """Convert a PipelineResult into a JSON-serializable dict."""
        return {
            "ok": result.ok,
            "video_path": result.video_path,
            "upgraded": result.upgraded.model_dump(),
            "code": result.code,
            "lint_issues": [i.model_dump() for i in result.lint_issues],
            "runtime_errors": result.runtime_errors,
            "logs": result.logs,
        }


def main(argv: list[str] | None = None) -> int:
    return _cli_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
