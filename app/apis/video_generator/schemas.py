from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class GenerateVideoRequest(BaseModel):
    prompt: str = Field(..., description="High-level instruction for the video")
    title: str = Field(..., description="Title for saving the video")
    description: str = Field("", description="Optional description for the video")

    # Advanced options (optional)
    scene_file: str = Field("scene.py")
    scene_name: str = Field("GeneratedScene")
    extra_packages: list[str] | None = Field(default=None)
    max_lint_batch_rounds: int = Field(2, ge=0, le=5)
    max_post_runtime_lint_rounds: int = Field(2, ge=0, le=5)
    max_runtime_fix_attempts: int = Field(2, ge=0, le=5)


class PipelineSummary(BaseModel):
    ok: bool
    video_path: Optional[str]
    lint_issues: list[dict]
    runtime_errors: list[str]


class GenerateVideoResponse(BaseModel):
    request_id: int
    video_uuid: str
    video_id: Optional[int]
    status: str
    pipeline: PipelineSummary
    status_url: str


class RequestStatusResponse(BaseModel):
    request_id: int
    video_uuid: str
    status: str
    started_at: str | None = None
    completed_at: str | None = None
    result_id: int | None = None
    video_id: int | None = None
    error_message: str | None = None


class VideoRead(BaseModel):
    id: int
    title: str
    description: str
    path: str
    original_path: str | None = None
    file_size: int | None = None
    duration: float | None = None
    uploaded_at: str


class RequestRead(BaseModel):
    id: int
    video_uuid: str
    status: str
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None
