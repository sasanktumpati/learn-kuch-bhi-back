"""Agents and utilities for generating, fixing, and running Manim code.

This module keeps pydantic-ai imports lazy so that utility helpers like
``run_lint`` and ``run_render`` can work without the full agent stack being
installed. Type annotations are postponed via ``from __future__ import
annotations``.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from pydantic import BaseModel, Field
from pydantic_ai import Agent, ModelRetry, Tool
from pydantic_ai._run_context import RunContext

from app.modules.video_generator.templates.manim_template import (
    MANIM_TIPS,
    default_manim_skeleton,
)

# Default model name for Google Gemini; OpenRouter model comes from settings
MODEL_NAME = "gemini-2.5-pro"
MANIM_LIBRARY_ID = "/manimcommunity/manim"
PYDANTIC_AI_LIBRARY_ID = "/pydantic/pydantic-ai"


def _build_google_model():
    """Build the Google Gemini model provider (lazy import)."""
    from pydantic_ai.models.google import GoogleModel
    from pydantic_ai.providers.google import GoogleProvider

    from app.core.config import settings

    api_key = settings.gemini_api_key
    provider = GoogleProvider(api_key=api_key)
    return GoogleModel(MODEL_NAME, provider=provider)


def _build_openrouter_model():
    """Build the OpenRouter model via the OpenAI-compatible provider (lazy import).

    Uses OpenRouter's OpenAI-compatible API endpoint. Model name and API key
    are read from settings.
    """
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.openai import OpenAIProvider

    from app.core.config import settings

    if not settings.openrouter_api_key:
        raise RuntimeError(
            "OpenRouter API key not configured. Set OPENROUTER_API_KEY in your environment."
        )

    provider = OpenAIProvider(
        api_key=settings.openrouter_api_key,
        base_url="https://openrouter.ai/api/v1",
        # Optionally set headers like HTTP-Referer / X-Title via provider args if needed.
    )
    model_name = settings.openrouter_model
    return OpenAIChatModel(model_name, provider=provider)


def _build_model_by_settings():
    """Return a pydantic-ai Model based on configured provider selection."""
    from app.core.config import settings

    provider = (settings.model_provider or "google").lower()
    if provider == "openrouter":
        return _build_openrouter_model()
    # default to Google
    return _build_google_model()


class ManimCode(BaseModel):
    """Structured output for generated Manim code."""

    scene_name: str = Field(..., description="Exact scene class name to render")
    code: str = Field(..., description="A complete manim Python file content")


class LintIssue(BaseModel):
    """Single Ruff issue entry parsed from JSON output."""

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


class PreflightResult(BaseModel):
    ok: bool
    stdout: str = ""
    stderr: str = ""


@dataclass
class SessionDeps:
    session_path: Path
    scene_file: str
    scene_name: str


SYSTEM_PROMPT = """
You are a senior Manim engineer focused on clear, correct, and
pedagogically effective animations. Generate production‑ready code that
renders cleanly and communicates ideas well.

Hard Rules
- Produce exactly one Scene subclass named exactly as requested.
- Implement construct(self); the file must render as‑is.
- Use only explicit imports from manim (no star imports). Keep imports minimal.
- Prefer APIs from the current stable Manim; use PI, TAU, E (no decimal constants).
- Keep code deterministic and self‑contained (no I/O, network, or randomness).

Structure and Style
- Organize the scene into small, clear sections; use helper methods if helpful.
- Use VGroup, alignment, and spacing (buff) to avoid overlaps.
- Ensure all content stays within the visible frame; nothing off‑screen.
- Ensure all text fits on screen; never let labels overlap or go off‑frame.
- Use self.wait(1–3) between logical steps and self.clear() when changing sections.
- Prefer smooth transitions: Create, Write, Transform, FadeIn/FadeOut.

Frame Safety
- Maintain safe margins from screen edges; scale or reposition as needed.
- Prevent overlaps using next_to(..., buff=...), arrange, and VGroup utilities.
- If space is limited, scale down or remove older elements before adding more.

Color and Emphasis
- Use named Manim colors. A sensible palette is: YELLOW/WHITE for titles,
  BLUE for primaries, GREEN for supporting elements, RED/ORANGE for emphasis,
  GRAY for reference (axes/grids). Be consistent.

Education‑First Guidance
- Build ideas progressively; label important objects and steps.
- Use MathTex for mathematics and arrows/highlights to direct attention.
- Add brief comments where the rationale isn’t obvious.

Imports and Dependencies
- Prefer only Manim imports; add others only if provided by the given template
  or clearly required for correctness.

Validation and Help
- If a documentation tool is available, consult it to confirm any uncertain API.

Output Contract
- Return only the complete Python file content and the exact scene_name; no
  markdown, fences, or extra commentary.
"""


def _build_context7_tool() -> Optional[Tool]:
    """Create a Context7 API tool if enabled/configured.

    Returns None when Context7 is disabled or no API key is present.
    """
    from app.core.config import settings
    from app.modules.video_generator.tools.context7_api import context7_tool

    if not settings.context7_enabled or not settings.context7_api_key:
        return None

    return Tool(context7_tool, takes_ctx=False)


def _make_ctx7_logger(on_snippet: Optional[Callable[[str], None]] = None):
    """Create a logger function for Context7 tool results."""
    if on_snippet is None:
        return lambda snippet: None

    def logger(snippet: str) -> None:
        try:
            # Extract first few lines for logging
            lines = snippet.splitlines()[:3]
            summary = " ".join(lines)
            on_snippet(summary)
        except Exception:
            pass

    return logger


def _parse_ruff_json(output: str, file_hint: str) -> list[LintIssue]:
    """Parse Ruff JSON output into LintIssue objects.

    Supports both array JSON and line-delimited JSON as a fallback.
    """
    issues: list[LintIssue] = []
    text = (output or "").strip()
    if not text:
        return issues
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
                    code=obj.get("code") or obj.get("rule", ""),
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


def _run(
    cwd: Path, *args: str, timeout_sec: Optional[float] = None
) -> subprocess.CompletedProcess:
    """Run a subprocess in ``cwd`` capturing output (text).

    If ``timeout_sec`` is provided, the process is terminated on timeout and a
    ``CompletedProcess``-like object is synthesized with non-zero returncode.
    """
    try:
        return subprocess.run(
            list(args),
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
    except (
        subprocess.TimeoutExpired
    ) as ex:  # defensive: ensure we never hang indefinitely
        return subprocess.CompletedProcess(
            args=list(args),
            returncode=124,
            stdout=ex.stdout.decode("utf-8", errors="ignore") if ex.stdout else "",
            stderr=(ex.stderr.decode("utf-8", errors="ignore") if ex.stderr else "")
            + f"\nTimed out after {timeout_sec}s running: {' '.join(args)}",
        )


def build_code_agent() -> "Agent[None, ManimCode]":
    from pydantic_ai import Agent

    model = _build_model_by_settings()

    # Build tools list
    tools = []
    context7_tool = _build_context7_tool()
    if context7_tool:
        tools.append(context7_tool)

    agent: Agent[None, ManimCode] = Agent[None, ManimCode](
        model,
        output_type=ManimCode,
        system_prompt=SYSTEM_PROMPT,
        # Retry model responses a few times for better self-correction
        retries=3,
        tools=tools,
    )
    return agent


def docs_tool() -> str:
    """Return curated tips from the Manim docs to guide the model."""
    return MANIM_TIPS


async def lint_tool(
    ctx: "RunContext[SessionDeps]", file_name: Optional[str] = None
) -> LintResult:
    """Run Ruff check and return structured issues."""
    file_name = file_name or ctx.deps.scene_file
    result = run_lint(ctx.deps.session_path, file_name)
    # If lint fails, ask the model to retry with corrections
    if not result.ok:
        # Provide a concise message; detailed issues are in result.issues/raw
        raise ModelRetry("Lint failed; fix Ruff issues and try again.")
    return result


async def render_tool(
    ctx: "RunContext[SessionDeps]",
    file_name: Optional[str] = None,
    scene_name: Optional[str] = None,
    quality: str = "-qm",
    output_base: str = "video",
) -> RenderResult:
    """Render the scene via ``uv run manim`` and return result (lint enforced)."""
    file_name = file_name or ctx.deps.scene_file
    scene_name = scene_name or ctx.deps.scene_name
    result = run_render(
        ctx.deps.session_path,
        file_name,
        scene_name,
        quality=quality,
        output_base=output_base,
    )
    # If rendering fails, encourage the model to adjust the code and retry
    if not result.ok:
        raise ModelRetry("Render failed; revise Manim code or imports and try again.")
    return result


def build_session_code_agent(deps: SessionDeps) -> "Agent[SessionDeps, ManimCode]":
    """Build a coding agent bound to a specific session with registered tools."""
    from pydantic_ai import Agent, Tool

    model = _build_model_by_settings()

    # Build tools list
    tools = [
        Tool(docs_tool, takes_ctx=False),
        # Tools for linting and rendering with context
        Tool(lint_tool, takes_ctx=True),
        Tool(render_tool, takes_ctx=True),
    ]

    # Add Context7 tool if available
    context7_tool = _build_context7_tool()
    if context7_tool:
        tools.append(context7_tool)

    agent: Agent[SessionDeps, ManimCode] = Agent[SessionDeps, ManimCode](
        model,
        output_type=ManimCode,
        system_prompt=SYSTEM_PROMPT,
        deps_type=SessionDeps,
        tools=tools,
        # Also give the model a few retries for output validation/self-correction
        retries=3,
    )
    return agent


def _build_generation_instruction(prompt: str, scene_name: str) -> str:
    skeleton = default_manim_skeleton(scene_name)
    instr = (
        f"Write a complete Manim file named class {scene_name}.\n"
        f"Follow these tips:\n{MANIM_TIPS}\n"
        f"You may adapt this skeleton but keep it valid:\n\n{json.dumps(skeleton)}\n\n"
        f"User prompt: {prompt}"
    )
    instr += (
        "\nIf available, use Context7 tool to fetch docs. "
        "Use use_manim=True for Manim documentation or use_manim=False for Pydantic-AI documentation as needed."
    )
    return instr


def generate_code_sync(prompt: str, scene_name: str = "GeneratedScene") -> ManimCode:
    agent: Agent[None, ManimCode] = build_code_agent()
    instruction = _build_generation_instruction(prompt, scene_name)
    return agent.run_sync(instruction, deps=None).output


def _build_fix_instruction(
    current_code: str, scene_name: str, upgraded_prompt: str, feedback: str
) -> str:
    instr = (
        "Revise the provided Manim code to address the feedback/errors.\n"
        "Keep the same scene class name. Maintain valid, runnable code.\n"
        f"Scene name: {scene_name}\n"
        f"Upgraded prompt: {upgraded_prompt}\n"
        f"Feedback to address (lint/runtime):\n{feedback}\n\n"
        f"Current code:\n{json.dumps(current_code)}\n"
    )
    instr += (
        "\nIf available, consult Context7 docs to guide fixes. "
        "Use use_manim=True for Manim documentation or use_manim=False for Pydantic-AI documentation as needed."
    )
    return instr


def fix_code_with_feedback_sync(
    current_code: str, scene_name: str, upgraded_prompt: str, feedback: str
) -> ManimCode:
    agent: Agent[None, ManimCode] = build_code_agent()
    instruction = _build_fix_instruction(
        current_code, scene_name, upgraded_prompt, feedback
    )
    return agent.run_sync(instruction, deps=None).output


async def generate_code(
    prompt: str,
    scene_name: str = "GeneratedScene",
    *,
    on_mcp_snippet: Optional[Callable[[str], None]] = None,
) -> ManimCode:
    """Async code generation to avoid nested event loop issues."""
    agent: Agent[None, ManimCode] = build_code_agent()
    instruction = _build_generation_instruction(prompt, scene_name)
    async with agent:
        res = await agent.run(instruction)
    return res.output


async def fix_code_with_feedback(
    current_code: str,
    scene_name: str,
    upgraded_prompt: str,
    feedback: str,
    *,
    on_mcp_snippet: Optional[Callable[[str], None]] = None,
) -> ManimCode:
    """Async fixer used during lint/runtime repair loops."""
    agent: Agent[None, ManimCode] = build_code_agent()
    instruction = _build_fix_instruction(
        current_code=current_code,
        scene_name=scene_name,
        upgraded_prompt=upgraded_prompt,
        feedback=feedback,
    )
    async with agent:
        res = await agent.run(instruction)
    return res.output


def run_lint(session_path: Path, file_name: str) -> LintResult:
    """Run Ruff on the given file inside the session directory."""

    def _run_ruff_json() -> subprocess.CompletedProcess:
        return _run(
            session_path,
            "uv",
            "run",
            "ruff",
            "check",
            "--fix",
            "--output-format",
            "json",
            file_name,
        )

    initial_proc = _run_ruff_json()
    initial_output = initial_proc.stdout or initial_proc.stderr
    issues = _parse_ruff_json(initial_output, file_name)
    issues = [i for i in issues if i.code != "F401"]

    if initial_proc.returncode == 0 and not issues:
        return LintResult(ok=True, issues=[], raw=initial_output)

    fix_proc = _run(
        session_path,
        "uv",
        "run",
        "ruff",
        "check",
        "--fix",
        file_name,
    )
    fix_output = fix_proc.stdout or fix_proc.stderr

    final_proc = _run_ruff_json()
    final_output = final_proc.stdout or final_proc.stderr
    issues = _parse_ruff_json(final_output, file_name)
    issues = [i for i in issues if i.code != "F401"]

    raw_segments = [
        segment for segment in (initial_output, fix_output, final_output) if segment
    ]
    return LintResult(
        ok=(final_proc.returncode == 0 and not issues),
        issues=issues,
        raw="\n".join(raw_segments),
    )


def run_render(
    session_path: Path,
    file_name: str,
    scene_name: str,
    *,
    quality: str = "-qm",
    output_base: str = "video",
) -> RenderResult:
    """Render the given scene via Manim inside the uv session.

    Lint is enforced before rendering to avoid wasting compute on a likely
    broken run.
    """
    lint = run_lint(session_path, file_name)
    if not lint.ok:
        return RenderResult(
            ok=False, stdout=lint.raw, stderr="Lint failed; fix issues before rendering"
        )

    # Apply a sane timeout so failed renders don't hang indefinitely.
    # This is a hard cap; typical -qm/-ql runs should finish well before this.
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
        timeout_sec=600,
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


def run_manim_preflight(session_path: Path) -> PreflightResult:
    """Attempt to import manim inside the session; return version output."""
    proc = _run(
        session_path,
        "uv",
        "run",
        "python",
        "-c",
        "import manim, sys; print(getattr(manim, '__version__', 'unknown')); sys.exit(0)",
    )
    return PreflightResult(
        ok=proc.returncode == 0, stdout=proc.stdout, stderr=proc.stderr
    )
