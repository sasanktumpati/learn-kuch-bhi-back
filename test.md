
- Model choice: Which LLM backend/model should we configure with pydantic-ai (e.g., OpenAI, Gemini, local)? Any org/project keys
already wired? -- yes use gemini-2.5-pro and get apikeys from config.py
- Runtime commands: OK to run shell commands in sessions (uv init/add, uv run ruff check, uv run manim …)? I’ll default to running -- yes, but keep that direcory as working directory
- Packages: Add ruff to the session env alongside manim and pydantic? Any pinned versions you want (e.g., manim==0.x, ruff==x.y)? -- no need to pin any versions
- Render path: Confirm outputs under generated_scenes/<video_id>/, filename from scene/class name, mp4 target? - yes
- Template: Any preferences for scene naming (e.g., TitleCase + “Scene”), color palette, fonts, or common imports to always
include? -- your wish. -- your wish
- Lint policy: Fail on any ruff error (exit non-zero), or only error-level (ignore warnings)? Preferred ruff flags (e.g.,
--select/--ignore)?   -- your wish, can ignore warnings
- Error reporting: Return structured errors (JSON-like) or human-readable text? Should we persist errors or just return them to
caller? -- your wish, which ever is better
- Docs use: OK if the coding agent uses a static, bundled “Manim quick-start + API tips” template, or do you want a tool that. 
injects curated docs snippets into context each run?  -- your choice, which ever is better, iam planning to add mcp to get docs later like context7 or we can get all and fetch from locally
- Orchestration API: Do you want a single pipeline entry (function) that:
    1. upgrades prompt, 2) generates code, 3) lints (loop until clean or N attempts), 4) renders (loop on runtime errors), 5)
returns final video path + code + logs? 
Or separate public entry points per stage? --  yes and for runtime errors after not fixed after one attempt, i need you to create a new agent with the code, the prompt to fix the errors and the errors and docs tool and the users upgraded prompt. also, after any one error is fixed, i say, spawn a new subagent to fix the other one so that we saty in context limits and that one agent can focus on doing that one thing better.
- Async vs sync: Prefer async agents and pipeline APIs, or sync wrappers?   -- async or sync, whichevr is better for my usecase

Proposed structure (high level)

- app/modules/video_generator/agents/
    - prompt_upgrader.py: Agent that outputs UpgradedPrompt(title, description, constraints).
    - code_generator.py: Agent that outputs ManimCode(scene_name, code). Tools:
    - lint_tool: runs uv run ruff check --format json <file.py>, returns structured issues.
    - render_tool : runs uv run manim -qm <file.py> <Scene>, returns output path or error.
    - docs_tool : returns curated manim tips/snippets from a local template.
- app/modules/video_generator/templates/manim_template.py: Starter scene/code guardrails and examples.
- app/modules/video_generator/pipeline.py: Orchestrates the full flow with mandatory lint-before-render and feedback loops.
- Reuse SessionEnv in utils/paths.py to create/init per-video uv env (install manim, pydantic, ruff) and manage paths.

and also, linting tool should be run everytime before running render so as to save time and compute.

Behavioral guarantees

- Always lint before any render, regardless of whether the agent chose to call the lint tool. 
- On lint failure: return a clean, structured summary and loop the agent to fix.
- On runtime/render error: capture stderr/logs, summarize cleanly, loop agent to fix.
- Use Manim docs patterns (e.g., manim -pql/-qm, Scene.construct()) per docs.
