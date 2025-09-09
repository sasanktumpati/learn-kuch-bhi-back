from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from pathlib import Path

from app.modules.video_generator.pipeline import run_video_pipeline


def _load_prompt(args: argparse.Namespace) -> str:
    if args.prompt and args.prompt_file:
        raise SystemExit("Provide either --prompt or --prompt-file, not both")
    if args.prompt_file:
        return Path(args.prompt_file).read_text(encoding="utf-8")
    if args.prompt:
        return args.prompt
    raise SystemExit("--prompt or --prompt-file is required")


def _print_human(result) -> None:
    print("=== Video Generator Result ===")
    print("ok:", result.ok)
    print("session:", result.logs.get("session_path"))
    print("video_path:", result.video_path)
    print("title:", result.upgraded.title)
    print("description:", result.upgraded.description)
    # Print first few lines of any Context7 MCP tool outputs captured by pipeline
    ctx7_snips = (result.logs or {}).get("context7_snippets") or []
    if ctx7_snips:
        print("\nContext7 MCP excerpts (first lines):")
        for i, snip in enumerate(ctx7_snips, start=1):
            head = "\n".join((snip or "").splitlines()[:5])
            print(f"[{i}] {head}")
    if result.lint_issues:
        print("\nLint issues:")
        for i in result.lint_issues:
            print(f"- {i.filepath}:{i.line}:{i.column} {i.code} {i.message}")
    if result.runtime_errors:
        print("\nRuntime errors:")
        for chunk in result.runtime_errors:
            print("---")
            print(chunk)


def _to_jsonable(result) -> dict:
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
    parser = argparse.ArgumentParser(
        prog="video-gen", description="Manim video generator CLI"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="Generate a Manim video from a prompt")
    g.add_argument("--prompt", "-p", help="User prompt (text)")
    g.add_argument("--prompt-file", help="Path to a file containing the prompt")
    g.add_argument("--video-id", help="Session/video id (default: random UUID)")
    g.add_argument("--scene-name", default="GeneratedScene", help="Scene class name")
    g.add_argument(
        "--scene-file", default="scene.py", help="Scene file name in session"
    )
    g.add_argument(
        "--extra",
        action="append",
        default=[],
        help="Extra packages to install in the session (repeatable)",
    )
    g.add_argument("--json", action="store_true", help="Output JSON instead of text")
    g.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress logs (useful for clean output)",
    )

    args = parser.parse_args(argv)
    if args.cmd == "generate":
        prompt = _load_prompt(args)
        video_id = args.video_id or str(uuid.uuid4())

        # Run pipeline
        # simple log printer to stderr so JSON (if any) stays on stdout
        def _log(msg: str) -> None:
            if not args.quiet:
                print(msg, file=sys.stderr, flush=True)

        result = asyncio.run(
            run_video_pipeline(
                prompt,
                video_id,
                scene_file=args.scene_file,
                scene_name=args.scene_name,
                extra_packages=list(args.extra) if args.extra else None,
                on_log=_log,
                uv_quiet=(args.quiet or args.json),
            )
        )

        if args.json:
            print(json.dumps(_to_jsonable(result), indent=2))
        else:
            _print_human(result)
        return 0 if result.ok else 1

    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
