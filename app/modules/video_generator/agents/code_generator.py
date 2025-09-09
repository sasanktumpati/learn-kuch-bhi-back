from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, cast


from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext, Tool
from pydantic_ai.models.google import GoogleModel, GoogleModelSettings
from pydantic_ai.providers.google import GoogleProvider

from app.core.config import settings
from app.modules.video_generator.templates.manim_template import (
    MANIM_TIPS,
    default_manim_skeleton,
)


MODEL_NAME = "gemini-2.5-pro"


def _build_google_model() -> GoogleModel:
    api_key = settings.gemini_api_key
    provider = GoogleProvider(api_key=api_key)
    return GoogleModel(
        MODEL_NAME,
        provider=provider,
    )


class ManimCode(BaseModel):
    scene_name: str = Field(..., description="Exact scene class name to render")
    code: str = Field(..., description="A complete manim Python file content")


class LintIssue(BaseModel):
    source: str = Field(default="ruff")
    code: str
    message: str
    filepath: str
    line: int
    column: int


class LintResult(BaseModel):
    ok: bool
    issues: list[LintIssue] = Field(default_factory=list)
    raw: str = Field(default="")


class RenderResult(BaseModel):
    ok: bool
    video_path: Optional[str] = None
    stdout: str = ""
    stderr: str = ""


@dataclass
class SessionDeps:
    session_path: Path
    scene_file: str
    scene_name: str


SYSTEM_PROMPT = (
    "You generate correct, lint-clean Manim code using Pydantic where helpful. "
    "Always produce a single class deriving from `Scene` named exactly as requested. "
    "Use imports `from manim import *` and keep code self-contained. "
    "Prefer simple, robust constructs from the Manim docs. Return complete file content."
)


def _parse_ruff_json(output: str, file_hint: str) -> list[LintIssue]:
    issues: list[LintIssue] = []
    text = output.strip()
    if not text:
        return issues
    # Try parse as one JSON per line (NDJSON) or a single JSON array
    try:
        data = json.loads(text)
        items = data if isinstance(data, list) else []
    except json.JSONDecodeError:
        items = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            items.append(obj)

    for obj in items:
        try:
            issues.append(
                LintIssue(
                    code=obj.get("code") or obj.get("rule"),
                    message=obj.get("message", ""),
                    filepath=obj.get("filename", file_hint),
                    line=int(
                        obj.get("location", {}).get("row")
                        or obj.get("location", {}).get("line")
                        or 0
                    ),
                    column=int(obj.get("location", {}).get("column") or 0),
                )
            )
        except Exception:
            continue
    return issues


def _run(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(list(args), cwd=str(cwd), capture_output=True, text=True)


def build_code_agent() -> Agent[ManimCode, str]:
    model = _build_google_model()
    agent: Agent[ManimCode, str] = Agent[ManimCode, str](
        model, output_type=ManimCode, system_prompt=SYSTEM_PROMPT
    )
    return agent


def docs_tool() -> str:
    """Return curated tips from the Manim docs to guide the model."""
    return MANIM_TIPS


async def lint_tool(
    ctx: RunContext[SessionDeps], file_name: Optional[str] = None
) -> LintResult:
    """Run ruff check and return structured issues. Ignores warnings if any."""
    file_name = file_name or ctx.deps.scene_file
    proc = _run(
        ctx.deps.session_path,
        "uv",
        "run",
        "ruff",
        "check",
        "--format",
        "json",
        file_name,
    )
    issues = _parse_ruff_json(proc.stdout or proc.stderr, file_name)
    return LintResult(
        ok=(proc.returncode == 0 and not issues),
        issues=issues,
        raw=(proc.stdout or proc.stderr),
    )


async def render_tool(
    ctx: RunContext[SessionDeps],
    file_name: Optional[str] = None,
    scene_name: Optional[str] = None,
    quality: str = "-qm",
    output_base: str = "video",
) -> RenderResult:
    """Render the scene via `uv run manim` and return result.

    Always run lint before rendering to save compute.
    """
    # Enforce lint first
    lint = await lint_tool(ctx, file_name)
    if not lint.ok:
        return RenderResult(
            ok=False, stderr="Lint failed; fix issues before rendering", stdout=lint.raw
        )

    file_name = file_name or ctx.deps.scene_file
    scene_name = scene_name or ctx.deps.scene_name
    # manim -qm -o <name> file.py SceneName
    proc = _run(
        ctx.deps.session_path,
        "uv",
        "run",
        "manim",
        quality,
        "-o",
        output_base,
        file_name,
        scene_name,
    )
    ok = proc.returncode == 0
    # Compute expected output path
    video_path = None
    if ok:
        # manim writes to media/videos/<file_name>/1080p60/<output_base>.mp4 by default; but -o sets base name.
        # To keep it simple, return session-local search for latest mp4.
        mp4s = sorted(Path(ctx.deps.session_path).rglob(f"{output_base}.mp4"))
        if mp4s:
            video_path = str(mp4s[-1])
    return RenderResult(
        ok=ok, video_path=video_path, stdout=proc.stdout, stderr=proc.stderr
    )


def build_session_code_agent(deps: SessionDeps) -> Agent[ManimCode, SessionDeps]:
    """Build a coding agent bound to a specific session with tools registered.

    Even if the agent does not call these tools, the pipeline enforces linting
    before any render. This function exists to make tools available to the model.
    """
    model = _build_google_model()
    agent: Agent[ManimCode, SessionDeps] = Agent[ManimCode, SessionDeps](
        model,
        output_type=ManimCode,
        system_prompt=SYSTEM_PROMPT,
        deps_type=SessionDeps,
        tools=[
            Tool(docs_tool, takes_ctx=False),
            Tool(lint_tool, takes_ctx=True),
            Tool(render_tool, takes_ctx=True),
        ],
    )
    # Attach deps at runtime via .run(..., deps=deps) if used interactively
    return agent


def generate_code_sync(prompt: str, scene_name: str = "GeneratedScene") -> ManimCode:
    agent: Agent[ManimCode, str] = build_code_agent()
    skeleton = default_manim_skeleton(scene_name)
    instruction = (
        f"Write a complete Manim file named class {scene_name}.\n"
        f"Follow these tips:\n{MANIM_TIPS}\n"
        f"You may adapt this skeleton but keep it valid:\n\n{json.dumps(skeleton)}\n\n"
        f"User prompt: {prompt}"
    )
    return cast(ManimCode, agent.run_sync(instruction).output)


def fix_code_with_feedback_sync(
    current_code: str,
    scene_name: str,
    upgraded_prompt: str,
    feedback: str,
) -> ManimCode:
    agent: Agent[ManimCode, str] = build_code_agent()
    instruction = (
        "Revise the provided Manim code to address the feedback/errors.\n"
        "Keep the same scene class name. Maintain valid, runnable code.\n"
        f"Scene name: {scene_name}\n"
        f"Upgraded prompt: {upgraded_prompt}\n"
        f"Feedback to address (lint/runtime):\n{feedback}\n\n"
        f"Current code:\n{json.dumps(current_code)}\n"
    )
    return cast(ManimCode, agent.run_sync(instruction).output)


async def generate_code(prompt: str, scene_name: str = "GeneratedScene") -> ManimCode:
    """Async code generation to avoid nested event loop issues."""
    agent: Agent[ManimCode, str] = build_code_agent()
    skeleton = default_manim_skeleton(scene_name)
    instruction = (
        f"Write a complete Manim file named class {scene_name}.\n"
        f"Follow these tips:\n{MANIM_TIPS}\n"
        f"You may adapt this skeleton but keep it valid:\n\n{json.dumps(skeleton)}\n\n"
        f"User prompt: {prompt}"
    )
    res = await agent.run(instruction)
    return cast(ManimCode, res.output)


async def fix_code_with_feedback(
    current_code: str,
    scene_name: str,
    upgraded_prompt: str,
    feedback: str,
) -> ManimCode:
    """Async fixer used during lint/runtime repair loops."""
    agent: Agent[ManimCode, str] = build_code_agent()
    instruction = (
        "Revise the provided Manim code to address the feedback/errors.\n"
        "Keep the same scene class name. Maintain valid, runnable code.\n"
        f"Scene name: {scene_name}\n"
        f"Upgraded prompt: {upgraded_prompt}\n"
        f"Feedback to address (lint/runtime):\n{feedback}\n\n"
        f"Current code:\n{json.dumps(current_code)}\n"
    )
    res = await agent.run(instruction)
    return cast(ManimCode, res.output)


# Non-tool helpers for pipeline usage (no RunContext required)
def run_lint(session_path: Path, file_name: str) -> LintResult:
    proc = _run(
        session_path, "uv", "run", "ruff", "check", "--format", "json", file_name
    )
    issues = _parse_ruff_json(proc.stdout or proc.stderr, file_name)
    return LintResult(
        ok=(proc.returncode == 0 and not issues),
        issues=issues,
        raw=(proc.stdout or proc.stderr),
    )


def run_render(
    session_path: Path,
    file_name: str,
    scene_name: str,
    *,
    quality: str = "-qm",
    output_base: str = "video",
) -> RenderResult:
    # Safety: lint first
    lint = run_lint(session_path, file_name)
    if not lint.ok:
        return RenderResult(
            ok=False, stdout=lint.raw, stderr="Lint failed; fix issues before rendering"
        )

    proc = _run(
        session_path,
        "uv",
        "run",
        "manim",
        quality,
        "-o",
        output_base,
        file_name,
        scene_name,
    )
    ok = proc.returncode == 0
    video_path = None
    if ok:
        mp4s = sorted(Path(session_path).rglob(f"{output_base}.mp4"))
        if mp4s:
            video_path = str(mp4s[-1])
    return RenderResult(
        ok=ok, video_path=video_path, stdout=proc.stdout, stderr=proc.stderr
    )
