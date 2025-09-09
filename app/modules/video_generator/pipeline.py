from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.modules.video_generator.agents.prompt_upgrader import (
    UpgradedPrompt,
    upgrade_prompt,
)
from app.modules.video_generator.agents.code_generator import (
    ManimCode,
    LintIssue,
    LintResult,
    RenderResult,
    generate_code,
    fix_code_with_feedback,
    run_lint,
    run_render,
)
from app.modules.video_generator.utils.paths import SessionEnv


@dataclass
class PipelineResult:
    ok: bool
    video_path: Optional[str]
    upgraded: UpgradedPrompt
    code: str
    lint_issues: list[LintIssue]
    runtime_errors: list[str]
    logs: dict


def _write_code(session_path: Path, file_name: str, code: str) -> Path:
    path = session_path / file_name
    path.write_text(code, encoding="utf-8")
    return path


async def _lint(session_path: Path, scene_file: str, scene_name: str) -> LintResult:
    return run_lint(session_path, scene_file)


async def _render(session_path: Path, scene_file: str, scene_name: str) -> RenderResult:
    return run_render(session_path, scene_file, scene_name)


async def run_video_pipeline(
    user_prompt: str,
    video_id: str,
    *,
    scene_file: str = "scene.py",
    scene_name: str = "GeneratedScene",
    extra_packages: list[str] | None = None,
) -> PipelineResult:
    # Prepare session environment with manim, pydantic, ruff
    env = SessionEnv(video_id)
    session_path = env.prepare(extra_packages=extra_packages)

    # 1) Upgrade prompt
    upgraded = await upgrade_prompt(user_prompt)

    # 2) Generate initial code
    code_resp: ManimCode = await generate_code(
        f"Title: {upgraded.title}\nDescription: {upgraded.description}\nConstraints: {upgraded.constraints}",
        scene_name=scene_name,
    )
    _write_code(session_path, scene_file, code_resp.code)

    # 3) Lint (mandatory) and fix loop per issue (one attempt each)
    lint = await _lint(session_path, scene_file, scene_name)
    fixed_any = False
    if not lint.ok and lint.issues:
        for issue in lint.issues:
            feedback = json.dumps(issue.model_dump(), indent=2)
            code_resp = await fix_code_with_feedback(
                current_code=(session_path / scene_file).read_text(encoding="utf-8"),
                scene_name=scene_name,
                upgraded_prompt=f"{upgraded.title}\n{upgraded.description}",
                feedback=f"Fix this single lint issue only: {feedback}",
            )
            _write_code(session_path, scene_file, code_resp.code)
            fixed_any = True
        # Re-run lint after attempting each issue once
        lint = await _lint(session_path, scene_file, scene_name)

    # 4) Render (only if lint clean)
    runtime_errors: list[str] = []
    video_path: Optional[str] = None
    if lint.ok:
        render_res = await _render(session_path, scene_file, scene_name)
        if render_res.ok and render_res.video_path:
            video_path = render_res.video_path
        else:
            # Runtime error -> spawn single-issue fix agents sequentially, one pass per error chunk
            # Keep the stderr as feedback; split into segments by lines containing 'ERROR' or 'Traceback'
            stderr = render_res.stderr or ""
            chunks: list[str] = []
            buf: list[str] = []
            for line in stderr.splitlines():
                if "ERROR" in line or "Traceback" in line:
                    if buf:
                        chunks.append("\n".join(buf))
                        buf = []
                buf.append(line)
            if buf:
                chunks.append("\n".join(buf))

            # If no chunks detected, use whole stderr once
            if not chunks and stderr:
                chunks = [stderr]

            for idx, chunk in enumerate(chunks or [stderr]):
                if not chunk:
                    continue
                runtime_errors.append(chunk)
                code_resp = await fix_code_with_feedback(
                    current_code=(session_path / scene_file).read_text(
                        encoding="utf-8"
                    ),
                    scene_name=scene_name,
                    upgraded_prompt=f"{upgraded.title}\n{upgraded.description}",
                    feedback=f"Runtime error segment {idx + 1}:\n{chunk}\nPlease fix only this problem, keep others intact.",
                )
                _write_code(session_path, scene_file, code_resp.code)
                # Lint again before re-rendering
                lint = await _lint(session_path, scene_file, scene_name)
                if not lint.ok:
                    break
                # Try render again after each fix
                render_res = await _render(session_path, scene_file, scene_name)
                if render_res.ok and render_res.video_path:
                    video_path = render_res.video_path
                    break

    ok = bool(video_path)
    logs = {
        "session_path": str(session_path),
        "lint_ok": lint.ok,
        "fixed_any": fixed_any,
    }
    return PipelineResult(
        ok=ok,
        video_path=video_path,
        upgraded=upgraded,
        code=(session_path / scene_file).read_text(encoding="utf-8"),
        lint_issues=lint.issues if not lint.ok else [],
        runtime_errors=runtime_errors,
        logs=logs,
    )
