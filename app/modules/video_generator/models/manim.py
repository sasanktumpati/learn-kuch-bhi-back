"""Pydantic models for Manim rendering via pydantic-ai."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import (
    BaseModel,
    Field,
    ConfigDict,
    AliasChoices,
    field_validator,
)
from pathlib import Path

from ..utils.paths import SessionEnv


class ManimConfig(BaseModel):
    """Configuration for Manim rendering.

    - `output_format` is constrained to mp4 to match pipeline expectations.
    - `frame_rate` is fixed to 30 by design.
    - `resolution` allows a simple `WxH` string (e.g., 1920x1080).
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    scene_name: str = Field(..., description="Name of the Manim scene to render")
    resolution: str = Field(
        "1920x1080",
        description="Resolution in 'WIDTHxHEIGHT' format (e.g., 1920x1080)",
    )
    frame_rate: Literal[30] = Field(
        30, description="Frame rate of the output video (fixed to 30)"
    )
    duration: int = Field(10, description="Duration of the video in seconds")
    output_format: Literal["mp4"] = Field(
        "mp4", description="Output video format (fixed to mp4)"
    )

    @field_validator("resolution")
    @classmethod
    def _validate_resolution(cls, v: str) -> str:
        if not re.fullmatch(r"\d{3,5}x\d{3,5}", v):
            raise ValueError("resolution must match 'WIDTHxHEIGHT', e.g. '1920x1080'")
        return v

    @field_validator("duration")
    @classmethod
    def _validate_duration(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("duration must be a positive integer (seconds)")
        return v


class ManimRenderRequest(BaseModel):
    """Request to render a Manim scene.

    - `script` is the raw Manim code (you may write to a temp file when executing).
    - `output_path` is a directory path, typically `generated_scenes/<video_id>`.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    config: ManimConfig = Field(..., description="Configuration for Manim rendering")
    script: str = Field(..., description="Manim script to be executed")
    output_path: str = Field(
        ..., description="Directory path to store render outputs and artifacts"
    )

    @field_validator("output_path")
    @classmethod
    def _validate_output_path(cls, v: str) -> str:
        norm = v.strip().replace("\\", "/")
        if norm.endswith(".mp4"):
            raise ValueError("output_path must be a directory, not a file path")
        if ".." in norm.split("/"):
            raise ValueError("output_path must not contain path traversal segments")
        if not (norm == "generated_scenes" or norm.startswith("generated_scenes/")):
            raise ValueError(
                "output_path must be under 'generated_scenes/' (e.g., generated_scenes/<video_id>)"
            )
        return norm


class ManimAIVideoResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(..., description="Title of the generated video")
    description: str = Field(..., description="Description of the generated video")
    code: str = Field(..., description="Generated Manim code")


class ManimAIVideoRunTimeFeedback(BaseModel):
    """Runtime feedback after attempting to render the AI-generated video."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        populate_by_name=True,
    )

    title: str = Field(..., description="Title of the video")
    description: str = Field(..., description="Description of the video")
    code: str = Field(..., description="Manim code for the video")
    feedback: str = Field(..., description="User feedback on the generated content")
    runtime_errors: str = Field(
        ...,
        description="Any errors encountered during rendering",
        validation_alias=AliasChoices("runtime_errors"),
    )


class ManimVideoLinterFeedback(BaseModel):
    """Linting feedback using tools like Ruff."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        populate_by_name=True,
    )

    title: str = Field(..., description="Title of the video")
    description: str = Field(..., description="Description of the video")
    code: str = Field(..., description="Manim code for the video")
    linter_feedback: str = Field(
        ...,
        description="Linter feedback on the generated code",
    )


def prepare_session_environment(
    request: ManimRenderRequest,
    *,
    extra_packages: list[str] | None = None,
    uv_quiet: bool = True,
) -> Path:
    """Create session directory and initialize it as a uv project.

    This convenience helper derives the session folder from ``request.output_path``
    (e.g., ``generated_scenes/<video_id>``), creates it if needed, and runs
    ``uv init`` + ``uv add`` for ``manim``, ``pydantic``, and any
    ``extra_packages`` you provide.

    Returns the resolved session directory path.
    """
    env = SessionEnv.from_output_path(request.output_path)
    env.prepare(extra_packages=extra_packages, uv_quiet=uv_quiet)
    return env.path
