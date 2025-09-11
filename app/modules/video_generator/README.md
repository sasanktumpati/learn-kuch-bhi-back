# Video Generator Module

Generate Manim videos from natural language prompts using a small agentic pipeline built on pydantic-ai. The pipeline upgrades the prompt, generates code, lints it, renders the video, and repairs issues via feedback loops.

## Overview
- Prompt upgrader agent rewrites the user prompt into a clearer, more descriptive brief.
- Coding agent produces a complete Manim scene (Python file) using best practices and Pydantic for simple configuration.
- Linting is mandatory (ruff) before any render to avoid wasted compute.
- Rendering runs via `manim` inside a per-video `uv` environment.
- On lint/runtime errors, subagents focus on one issue at a time to repair code and keep context tight.

Key tech:
- pydantic-ai (agents, tools)
- Manim (rendering)
- uv (per-session isolated environment)
- ruff (linting)

## Directory Structure
- `agents/`
  - `prompt_upgrader.py`: Upgrades user prompts into a structured brief.
  - `code_generator.py`: Generates/fixes Manim code and exposes lint/render tools.
- `templates/`
  - `manim_template.py`: Minimal scene skeleton and curated Manim tips.
- `utils/`
  - `paths.py`: `SessionEnv` to create and initialize session folders with uv.
- `pipeline.py`: Orchestrates the full flow end-to-end.
- `models/`: Pydantic models for Manim configs and requests.

## Prerequisites
- Python: repo targets `>=3.13` (see `pyproject.toml`).
- uv CLI installed (https://docs.astral.sh/uv/):
  - macOS/Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
  - Windows (PowerShell): `irm https://astral.sh/uv/install.ps1 | iex`
- Manim system dependencies (OS packages) if not already installed:
  - FFmpeg, Cairo, Pango, FreeType, pkg-config, etc. See Manim install docs for your OS.
- LLM provider and keys in your environment (read by `app/core/config.py`):
  - Default provider is Google Gemini. For Gemini:
    - `MODEL_PROVIDER=google`
    - `GEMINI_API_KEY=your_api_key_here`
  - To use OpenRouter (OpenAI-compatible):
    - `MODEL_PROVIDER=openrouter`
    - `OPENROUTER_API_KEY=your_api_key_here`
    - `OPENROUTER_MODEL=anthropic/claude-3.5-sonnet` (or your preferred model id)

## Session Environment (uv)
Each render session runs in `generated_scenes/<video_id>/` and is initialized as a uv project:
- `uv init` (once per session folder)
- `uv add manim pydantic ruff`

This isolates Python packages and ensures reproducibility and minimal cross-project interference. All lint/render commands use the session directory as the working directory.

## Programmatic Usage
Minimal, end-to-end run:

```python
import asyncio
from app.modules.video_generator.pipeline import run_video_pipeline

async def main():
    result = await run_video_pipeline(
        user_prompt="Animate the Pythagorean theorem with labeled squares and a short proof.",
        video_id="example-1234",
    )

    if result.ok:
        print("Video:", result.video_path)
    else:
        print("Failed. Lint issues:", [i.model_dump() for i in result.lint_issues])
        print("Runtime errors:", result.runtime_errors)
    print("Upgraded prompt:", result.upgraded.model_dump())

asyncio.run(main())
```

What you get back:
- `ok`: True if a video was successfully rendered.
- `video_path`: Path to the produced `.mp4` inside the session folder.
- `upgraded`: The improved prompt with `title`, `description`, `constraints`.
- `code`: The final Manim Python source stored in the session.
- `lint_issues`: Structured ruff findings if linting failed.
- `runtime_errors`: A list of summarized error segments if rendering failed.
- `logs`: Misc info (session path, whether fixes were attempted, etc.).

## Pipeline Details
- Prompt upgrading uses the Gemini model `google-gla:gemini-2.5-pro`; the API key comes from `settings.gemini_api_key` (via `GEMINI_API_KEY`).
- Code generation uses a small system prompt, curated Manim tips, and a minimal Pydantic-backed skeleton (`templates/manim_template.py`).
- Linting uses `uv run ruff check --output-format json`, and any issues block rendering.
- Rendering uses `uv run manim -qm -o video scene.py <SceneName>`; the pipeline searches for the produced `video.mp4`.
- Feedback loops:
  - Lint errors: the pipeline spawns a focused “fix” subagent per issue (one pass each), then re-lints.
  - Runtime errors: the pipeline segments stderr (ERROR/Traceback lines) and spawns one fix subagent per segment; lint and re-render after each fix.

## Customization
- Template and tips: Edit `templates/manim_template.py` to guide the code generator.
- Scene name/file: Change `scene_name` and/or `scene_file` when calling `run_video_pipeline()`.
- Packages: `SessionEnv.prepare()` installs `manim`, `pydantic`, and `ruff` by default; add extras via `extra_packages` if you extend the pipeline.
- Lint policy: The pipeline treats all ruff findings as blocking. You can adjust the ruff invocation and parsing logic in `agents/code_generator.py` if you want to accept warnings.

## Using Agents Directly (Advanced)
You can run the agents outside the pipeline for custom flows:

```python
# Upgrade prompt
from app.modules.video_generator.agents.prompt_upgrader import upgrade_prompt_sync
upgraded = upgrade_prompt_sync("Make an animation about Fibonacci spirals.")

# Generate code with context
from app.modules.video_generator.agents.code_generator import generate_code_sync
code = generate_code_sync(
    prompt=f"Title: {upgraded.title}\nDescription: {upgraded.description}",
    scene_name="FibonacciScene",
)

# Prepare session and write code
from app.modules.video_generator.utils.paths import SessionEnv
sess = SessionEnv("fib-0001").prepare()
(scene_path := (sess / "scene.py")).write_text(code.code)

# Lint and render
from app.modules.video_generator.agents.code_generator import run_lint, run_render
lint_res = run_lint(sess, "scene.py")
if lint_res.ok:
    render_res = run_render(sess, "scene.py", "FibonacciScene")
    print(render_res.video_path)
else:
    print("Lint issues:", [i.model_dump() for i in lint_res.issues])
```

## Troubleshooting
- `uv: command not found`: Install uv and ensure it’s on PATH.
- Manim system dependencies: If `manim` fails to import or render, ensure FFmpeg/Cairo/Pango/etc. are installed for your OS.
- Missing API key: Set `GEMINI_API_KEY` in `.env` or your environment.
- No video after render: Check stderr in the `PipelineResult.logs` or the session folder output; fix runtime errors via the automatic loop or adjust the prompt.

## Development
- Types: run `ty check` (if installed) to validate typing.
- Code style: linting uses `ruff` inside session folders before rendering.
- Extensibility: add new tools (e.g., test runner, asset fetcher) via `pydantic-ai Tool` in `code_generator.py` and register them in the agent.

## Notes
- The pipeline uses curated Manim tips now; in the future, you can swap in an MCP-backed docs tool (e.g., Context7 or local cache) without changing the orchestration.
- All shell commands run with the session directory as the working directory to avoid polluting the repo.
## CLI Usage
Run the generator from the command line without writing glue code.

Option A: module entry
- `python -m app.modules.video_generator.cli generate --prompt "Draw a circle morphing into a square" --video-id demo-001`
- `python -m app.modules.video_generator.cli generate --prompt-file prompt.txt --scene-name MyScene`
- `python -m app.modules.video_generator.cli generate -p "Euler's formula" --extra numpy --extra sympy --json`

Option B: add a script entry (optional)
You can add a console script to `pyproject.toml` to get a `video-gen` command. Example:

```
[project.scripts]
video-gen = "app.modules.video_generator.cli:main"
```

Then run:
- `video-gen generate --prompt "Animate the binomial expansion" --video-id v-123`
- `video-gen generate --prompt-file examples/prompt.md --scene-file theorem.py --scene-name TheoremScene`

Flags
- `--prompt` / `--prompt-file`: Provide the user prompt (one is required)
- `--video-id`: Session id (defaults to a random UUID)
- `--scene-name`: Scene class name (default: GeneratedScene)
- `--scene-file`: Python file name (default: scene.py)
- `--extra`: Extra packages to `uv add` in the session (repeatable)
- `--json`: Emit a JSON result to stdout
