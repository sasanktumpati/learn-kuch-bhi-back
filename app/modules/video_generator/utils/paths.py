"""Utilities for resolving and creating session-specific paths.

Conventions:
- All artifacts live under `generated_scenes/`.
- Each rendering session uses a subdirectory named after the video_id (UUID).

This module provides a ``SessionEnv`` class to manage a session directory as an
isolated `uv` project (``uv init`` + ``uv add``) and to build safe output paths.
"""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
from typing import Iterable, Sequence
import re

_SAFE_SEGMENT_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def _safe_segment(segment: str) -> str:
    """Ensure a single path segment is safe (no separators, no traversal).

    Allows alphanumerics, dash, underscore, and dot.
    """
    if segment in {"", ".", ".."}:
        raise ValueError("Invalid path segment")
    if not _SAFE_SEGMENT_RE.fullmatch(segment):
        raise ValueError("Path segment contains unsupported characters")
    return segment


def _run(cmd: Sequence[str], cwd: Path) -> None:
    """Run a command, raising a RuntimeError on failure.

    The command's stdout/stderr are inherited so the caller can see progress
    when run interactively. This function assumes the caller has already
    ensured `cwd` exists.
    """
    try:
        subprocess.run(list(cmd), cwd=str(cwd), check=True)
    except FileNotFoundError as exc:
        raise RuntimeError(f"Command not found: {cmd[0]}") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"Command failed with exit code {exc.returncode}: {' '.join(cmd)}"
        ) from exc


class SessionEnv:
    """Manage a video session folder and its uv environment.

    - Creates the session directory (``ensure_dir``)
    - Initializes ``uv`` and adds packages (``ensure_uv``)
    - Builds safe output paths (``output_video_path``)

    You can also build from a precomputed output directory via
    ``SessionEnv.from_output_path(output_path)``.
    """

    def __init__(
        self, video_id: str, base_dir: Path | str = "generated_scenes"
    ) -> None:
        self.base_dir = Path(base_dir)
        self.video_id = _safe_segment(str(video_id))
        self.path = self.base_dir / self.video_id

    @classmethod
    def from_output_path(cls, output_path: str) -> "SessionEnv":
        norm = output_path.strip().replace("\\", "/")
        if norm.endswith(".mp4"):
            raise ValueError("output_path must be a directory, not a file path")
        if ".." in norm.split("/"):
            raise ValueError("output_path must not contain path traversal segments")
        if not (norm == "generated_scenes" or norm.startswith("generated_scenes/")):
            raise ValueError(
                "output_path must be under 'generated_scenes/' (e.g., generated_scenes/<video_id>)"
            )
        p = Path(norm)
        return cls(video_id=p.name, base_dir=p.parent or Path("generated_scenes"))

    def ensure_dir(self) -> Path:
        self.path.mkdir(parents=True, exist_ok=True)
        return self.path

    def ensure_uv(
        self, packages: Iterable[str] | None = None, quiet: bool = True
    ) -> None:
        if not self.path.exists():
            raise ValueError("session_path does not exist; call ensure_dir() first")

        if shutil.which("uv") is None:
            raise RuntimeError(
                "`uv` CLI not found on PATH. Install it from https://docs.astral.sh/uv/"
            )

        pyproject = self.path / "pyproject.toml"
        qflag = ["-q"] if quiet else []

        if not pyproject.exists():
            _run(["uv", "init", *qflag], cwd=self.path)

        to_add = list(packages) if packages else ["manim", "pydantic"]
        if to_add:
            _run(["uv", "add", *qflag, *to_add], cwd=self.path)

    def output_path_for(self, scene_name: str, ext: str = "mp4") -> Path:
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", scene_name).strip("._-") or "scene"
        return self.path / f"{safe}.{ext}"

    def prepare(
        self, extra_packages: Iterable[str] | None = None, uv_quiet: bool = True
    ) -> Path:
        """Create directory and initialize uv with base + extras. Returns path.

        Base packages include manim, pydantic, and ruff (for linting).
        """
        self.ensure_dir()
        base = ["manim", "pydantic", "ruff"]
        packages = [*base, *(list(extra_packages) if extra_packages else [])]
        self.ensure_uv(packages=packages, quiet=uv_quiet)
        return self.path
