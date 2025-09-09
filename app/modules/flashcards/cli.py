from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.modules.flashcards.main import MultiFlashcardsGenerator


def _load_prompt(args: argparse.Namespace) -> str:
    if args.prompt and args.prompt_file:
        raise SystemExit("Provide either --prompt or --prompt-file, not both")
    if args.prompt_file:
        return Path(args.prompt_file).read_text(encoding="utf-8")
    if args.prompt:
        return args.prompt
    raise SystemExit("--prompt or --prompt-file is required")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="flashcards-gen", description="Flashcards generator CLI"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    gm = sub.add_parser(
        "generate-multi",
        help="Generate an outline and flashcards per subtopic (multi-agent; AI decides counts)",
    )
    gm.add_argument("--prompt", "-p", help="User prompt/topic (text)")
    gm.add_argument("--prompt-file", help="Path to a file containing the prompt")
    gm.add_argument(
        "--concurrency", type=int, default=6, help="Concurrent subagents limit"
    )
    gm.add_argument("--json", action="store_true", help="Output JSON (default)")

    args = parser.parse_args(argv)
    if args.cmd == "generate-multi":
        prompt = _load_prompt(args)
        svc = MultiFlashcardsGenerator(concurrency=args.concurrency)
        result = svc.generate_sync(prompt)
        print(json.dumps(result.model_dump(), indent=2))
        return 0

    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
