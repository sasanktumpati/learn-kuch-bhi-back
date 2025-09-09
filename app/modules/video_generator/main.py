"""Video generator service class and module entrypoint.

Provides a small, API-friendly wrapper class around the pipeline so your
endpoints or background jobs can call it directly. The module also remains
executable as a convenience entrypoint that delegates to the CLI.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Callable, Optional

from app.modules.video_generator.pipeline import PipelineResult, run_video_pipeline
from app.modules.video_generator.cli import main as _cli_main


class VideoGenerator:
    """High-level service for generating Manim videos.
    Example (async):
        svc = VideoGenerator()
        result = await svc.generate("Animate Pythagoras", video_id="vid-123")

    Example (sync):
        svc = VideoGenerator()
        result = svc.generate_sync("Animate Pythagoras")
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
