"""Convenience entrypoint to run the video generator CLI.

This simply delegates to ``app.modules.video_generator.cli.main`` so that
``python -m app.modules.video_generator.main`` works in addition to the CLI.
"""

from __future__ import annotations

from app.modules.video_generator.cli import main as _cli_main


def main(argv: list[str] | None = None) -> int:
    return _cli_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
