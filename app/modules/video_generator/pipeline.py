"""End-to-end pipeline to upgrade a prompt, generate Manim code, lint, and render."""

from __future__ import annotations

import json
from dataclasses import dataclass
import shutil
from pathlib import Path
from typing import Callable, Optional

from app.modules.video_generator.agents.prompt_upgrader import (
    UpgradedPrompt,
    upgrade_prompt,
)
from app.modules.video_generator.agents.code_generator import (
    ManimCode,
    LintIssue,
    LintResult,
    PreflightResult,
    generate_code,
    fix_code_with_feedback,
    run_lint,
    run_render,
    run_manim_preflight,
)
from app.modules.video_generator.utils.paths import SessionEnv
from app.core.config import settings


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


async def run_video_pipeline(
    user_prompt: str,
    video_id: str,
    *,
    scene_file: str = "scene.py",
    scene_name: str = "GeneratedScene",
    extra_packages: list[str] | None = None,
    on_log: Optional[Callable[[str], None]] = None,
    uv_quiet: bool = False,
    max_lint_batch_rounds: int = 2,
    max_post_runtime_lint_rounds: int = 2,
    max_runtime_fix_attempts: int = 2,
) -> PipelineResult:
    def _log(msg: str) -> None:
        if on_log is not None:
            on_log(msg)
        else:
            print(msg, flush=True)

    _log(f"[video:{video_id}] Starting pipeline")

    env = SessionEnv(video_id)
    _log("Preparing session environment (uv init + add)...")
    session_path = env.prepare(extra_packages=extra_packages, uv_quiet=uv_quiet)
    _log(f"Session directory: {session_path}")

    if settings.context7_enabled and settings.context7_api_key:
        _log("Context7 API: enabled")
    else:
        _log("Context7 API: disabled or missing API key")

    _log("Upgrading prompt with Gemini...")
    upgraded = await upgrade_prompt(user_prompt)
    _log(f"Upgraded prompt title: {upgraded.title}")

    _log("Generating initial Manim code...")
    ctx7_snippets: list[str] = []

    def _ctx7_log(snippet: str) -> None:
        ctx7_snippets.append(snippet)
        _log("[ctx7] " + (" ".join(snippet.splitlines()[:1]) if snippet else "(empty)"))

    code_resp: ManimCode = await generate_code(
        f"Title: {upgraded.title}\nDescription: {upgraded.description}\nConstraints: {upgraded.constraints}",
        scene_name=scene_name,
        on_mcp_snippet=_ctx7_log,
    )
    path_written = _write_code(session_path, scene_file, code_resp.code)
    _log(f"Wrote scene to {path_written}")

    fixed_any = False

    async def _batch_fix(
        current_lint: LintResult, *, label: str, rounds: int
    ) -> LintResult:
        nonlocal fixed_any
        lint_local = current_lint
        for round_num in range(1, rounds + 1):
            issues_json = json.dumps(
                [i.model_dump() for i in lint_local.issues], indent=2
            )
            _log(
                f"Fixing {len(lint_local.issues)} {label} issues in batch (round {round_num}/{rounds})..."
            )
            code_resp = await fix_code_with_feedback(
                current_code=(session_path / scene_file).read_text(encoding="utf-8"),
                scene_name=scene_name,
                upgraded_prompt=f"{upgraded.title}\n{upgraded.description}",
                feedback=(
                    "Fix ALL of the following Ruff issues in one pass.\n"
                    "Do not introduce star imports. Keep the same scene class name.\n"
                    f"Issues (JSON array):\n{issues_json}\n"
                ),
                on_mcp_snippet=_ctx7_log,
            )
            _write_code(session_path, scene_file, code_resp.code)
            fixed_any = True

            _log("Re-running Ruff after batch fixes...")
            lint_local = run_lint(session_path, scene_file)
            _log(
                "Ruff: clean"
                if lint_local.ok
                else f"Ruff: {len(lint_local.issues)} issue(s) remain"
            )
            if lint_local.ok or not lint_local.issues:
                break
        return lint_local

    _log("Running Ruff lint...")
    lint = run_lint(session_path, scene_file)
    _log("Ruff: clean" if lint.ok else f"Ruff: {len(lint.issues)} issue(s) detected")
    if not lint.ok:
        raw_head = "\n".join((lint.raw or "").splitlines()[:20]).strip()
        if raw_head:
            _log("Ruff raw output (head):\n" + raw_head)
    if not lint.ok and lint.issues:
        _log("Ruff issues (batch):")
        for i in lint.issues:
            _log(f"- {i.filepath}:{i.line}:{i.column} {i.code} {i.message}")

        lint = await _batch_fix(lint, label="lint", rounds=max_lint_batch_rounds)

        if not lint.ok:
            _log(
                "Lint still failing after batch fixes; regenerating code with a fresh agent..."
            )
            regen_feedback = (
                "Regenerate the entire Manim file from scratch.\n"
                "Satisfy all Ruff lint rules. Use explicit imports only.\n"
                "Avoid LaTeX (MathTex/Tex) if a LaTeX compiler is unavailable.\n"
                "Keep the scene class name identical and code self-contained.\n"
            )
            code_resp = await generate_code(
                f"Title: {upgraded.title}\nDescription: {upgraded.description}\nConstraints: {upgraded.constraints}\n{regen_feedback}",
                scene_name=scene_name,
                on_mcp_snippet=_ctx7_log,
            )
            _write_code(session_path, scene_file, code_resp.code)

            # Comprehensive fix loop after initial regeneration
            _log("Running comprehensive lint fix loop after initial regeneration...")
            initial_regen_attempts = 0
            max_initial_regen_attempts = 2

            while initial_regen_attempts < max_initial_regen_attempts:
                _log("Re-running Ruff after regeneration...")
                lint = run_lint(session_path, scene_file)
                if lint.ok:
                    _log("Ruff: clean after regeneration")
                    break
                elif lint.issues:
                    _log(f"Ruff: {len(lint.issues)} issue(s) remain after regeneration")
                    lint = await _batch_fix(
                        lint,
                        label="post-initial-regeneration lint",
                        rounds=max_lint_batch_rounds,
                    )
                    if lint.ok:
                        break
                    initial_regen_attempts += 1
                    if initial_regen_attempts < max_initial_regen_attempts:
                        _log(
                            "Attempting one more regeneration to fix remaining lint issues..."
                        )
                        code_resp = await generate_code(
                            f"Title: {upgraded.title}\nDescription: {upgraded.description}\nConstraints: {upgraded.constraints}\n{regen_feedback}\nFocus on fixing lint issues from previous attempt.",
                            scene_name=scene_name,
                            on_mcp_snippet=_ctx7_log,
                        )
                        _write_code(session_path, scene_file, code_resp.code)
                else:
                    _log("No specific lint issues found but Ruff still failing")
                    break

    runtime_errors: list[str] = []
    video_path: Optional[str] = None
    if lint.ok:
        _log("Preflight: checking Manim import inside session...")
        pre: PreflightResult = run_manim_preflight(session_path)
        if pre.ok:
            head = "\n".join((pre.stdout or "").splitlines()[:3]).strip()
            _log(f"Preflight OK (manim version): {head or 'unknown'}")
        else:
            err_head = "\n".join((pre.stderr or pre.stdout or "").splitlines()[:8])
            _log("Preflight FAILED. First lines:\n" + err_head)

        if shutil.which("latex") is None:
            _log(
                "LaTeX not found on PATH. Rewriting code to avoid MathTex/Tex usage..."
            )
            code_resp = await fix_code_with_feedback(
                current_code=(session_path / scene_file).read_text(encoding="utf-8"),
                scene_name=scene_name,
                upgraded_prompt=f"{upgraded.title}\n{upgraded.description}",
                feedback=(
                    "The execution environment does not have a LaTeX compiler ('latex').\n"
                    "Remove all uses of MathTex/Tex and any LaTeX templating.\n"
                    "Replace them with Text using Unicode characters (e.g., '90°', '45°').\n"
                    "Keep the same visual intent and positioning as much as possible.\n"
                    "Ensure explicit imports only (no star imports)."
                ),
                on_mcp_snippet=_ctx7_log,
            )
            _write_code(session_path, scene_file, code_resp.code)
            _log("Code rewritten to avoid LaTeX; re-running Ruff...")
            lint = run_lint(session_path, scene_file)
            _log(
                "Ruff: clean" if lint.ok else "Ruff: issues remain after LaTeX rewrite"
            )

        _log("Rendering with Manim (this can take a while)...")
        render_res = run_render(session_path, scene_file, scene_name)
        if render_res.ok and render_res.video_path:
            video_path = render_res.video_path
            _log(f"Render complete: {video_path}")
        else:
            _log("Render failed; attempting focused fixes from error output...")
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

            if not chunks:
                head = "\n".join(
                    (render_res.stderr or render_res.stdout or "").splitlines()[:12]
                )
                if head:
                    _log("Render failed. Output excerpt:\n" + head)
                if render_res.stderr:
                    chunks = [render_res.stderr]

            attempts = 0
            for idx, chunk in enumerate(chunks or [stderr]):
                if not chunk:
                    continue
                runtime_errors.append(chunk)
                _log(f"Fixing runtime error segment {idx + 1}/{len(chunks)}...")
                code_resp = await fix_code_with_feedback(
                    current_code=(session_path / scene_file).read_text(
                        encoding="utf-8"
                    ),
                    scene_name=scene_name,
                    upgraded_prompt=f"{upgraded.title}\n{upgraded.description}",
                    feedback=f"Runtime error segment {idx + 1}:\n{chunk}\nPlease fix only this problem, keep others intact.",
                    on_mcp_snippet=_ctx7_log,
                )
                _write_code(session_path, scene_file, code_resp.code)

                _log("Re-running Ruff after runtime fix...")
                lint = run_lint(session_path, scene_file)
                if not lint.ok:
                    _log("Ruff not clean after fix; attempting batch lint fixes...")

                    raw_head = "\n".join((lint.raw or "").splitlines()[:20]).strip()
                    if raw_head:
                        _log("Ruff raw output (head):\n" + raw_head)

                    if lint.issues:
                        _log("Ruff issues (post-runtime batch):")
                        for i in lint.issues:
                            _log(
                                f"- {i.filepath}:{i.line}:{i.column} {i.code} {i.message}"
                            )
                        lint = await _batch_fix(
                            lint,
                            label="post-runtime lint",
                            rounds=max_post_runtime_lint_rounds,
                        )

                    if not lint.ok:
                        _log("Ruff still not clean; aborting further renders.")
                        break

                _log("Re-rendering after fix...")
                render_res = run_render(session_path, scene_file, scene_name)
                if render_res.ok and render_res.video_path:
                    video_path = render_res.video_path
                    _log(f"Render complete: {video_path}")
                    break
                attempts += 1
                if attempts >= max_runtime_fix_attempts:
                    _log(
                        "Still failing after multiple runtime fix attempts; regenerating code with a fresh agent..."
                    )
                    regen_feedback = (
                        "Regenerate the entire Manim file from scratch.\n"
                        "Address prior runtime errors and keep imports explicit.\n"
                        "Avoid LaTeX (MathTex/Tex) if a LaTeX compiler is unavailable.\n"
                        "Keep the scene class name identical and code self-contained.\n"
                    )
                    code_resp = await generate_code(
                        f"Title: {upgraded.title}\nDescription: {upgraded.description}\nConstraints: {upgraded.constraints}\n{regen_feedback}",
                        scene_name=scene_name,
                        on_mcp_snippet=_ctx7_log,
                    )
                    _write_code(session_path, scene_file, code_resp.code)

                    # Comprehensive fix loop after regeneration
                    _log("Running comprehensive fix loop after regeneration...")
                    regen_attempts = 0
                    max_regen_attempts = 3

                    while regen_attempts < max_regen_attempts:
                        # Check and fix lint issues
                        _log("Re-running Ruff after regeneration...")
                        lint = run_lint(session_path, scene_file)
                        if not lint.ok and lint.issues:
                            _log(
                                f"Ruff: {len(lint.issues)} issue(s) found after regeneration"
                            )
                            lint = await _batch_fix(
                                lint,
                                label="post-regeneration lint",
                                rounds=max_lint_batch_rounds,
                            )
                            if not lint.ok:
                                _log(
                                    "Lint still failing after regeneration fixes; trying once more..."
                                )
                                regen_attempts += 1
                                continue
                        elif not lint.ok:
                            _log("Ruff not clean after regeneration; aborting.")
                            break

                        # Try rendering
                        _log("Re-rendering after regeneration and fixes...")
                        render_res = run_render(session_path, scene_file, scene_name)
                        if render_res.ok and render_res.video_path:
                            video_path = render_res.video_path
                            _log(f"Render complete after regeneration: {video_path}")
                            break
                        else:
                            # Handle render errors with targeted fixes
                            _log(
                                "Render still failing after regeneration; attempting targeted fixes..."
                            )
                            stderr = render_res.stderr or ""
                            if stderr and regen_attempts < max_regen_attempts - 1:
                                code_resp = await fix_code_with_feedback(
                                    current_code=(session_path / scene_file).read_text(
                                        encoding="utf-8"
                                    ),
                                    scene_name=scene_name,
                                    upgraded_prompt=f"{upgraded.title}\n{upgraded.description}",
                                    feedback=f"Post-regeneration render error:\n{stderr[:1000]}\nFix this specific issue while maintaining code quality.",
                                    on_mcp_snippet=_ctx7_log,
                                )
                                _write_code(session_path, scene_file, code_resp.code)
                                regen_attempts += 1
                            else:
                                _log(
                                    "Render still failing after all regeneration attempts; aborting."
                                )
                                break

                    if regen_attempts >= max_regen_attempts and not (
                        render_res.ok and render_res.video_path
                    ):
                        _log("Maximum regeneration attempts reached; aborting.")
                        break

    ok = bool(video_path)
    logs = {
        "session_path": str(session_path),
        "lint_ok": lint.ok,
        "fixed_any": fixed_any,
        "context7_snippets": ctx7_snippets,
    }
    _log(f"[video:{video_id}] Finished with status: {'ok' if ok else 'failed'}")
    return PipelineResult(
        ok=ok,
        video_path=video_path,
        upgraded=upgraded,
        code=(session_path / scene_file).read_text(encoding="utf-8"),
        lint_issues=lint.issues if not lint.ok else [],
        runtime_errors=runtime_errors,
        logs=logs,
    )
