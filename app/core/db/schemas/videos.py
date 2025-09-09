from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
    Enum,
    JSON,
    Boolean,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.core.db.base import Base

if TYPE_CHECKING:
    from .auth import User


class RenderStatus(enum.Enum):
    PENDING = "pending"
    QUEUED = "queued"
    STARTED = "started"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class GenerationStatus(enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Videos(Base):
    __tablename__ = "videos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    path: Mapped[str] = mapped_column(
        String, nullable=False
    )  # Final video path for serving
    original_path: Mapped[str] = mapped_column(
        String, nullable=True
    )  # Original generated path
    file_size: Mapped[int] = mapped_column(Integer, nullable=True)  # File size in bytes
    duration: Mapped[float] = mapped_column(
        Integer, nullable=True
    )  # Duration in seconds
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    user: Mapped["User"] = relationship("User", back_populates="videos")
    codes: Mapped[list["VideoCodes"]] = relationship(
        "VideoCodes", back_populates="video", cascade="all, delete-orphan"
    )
    generation_results: Mapped[list["VideoGenerationResult"]] = relationship(
        "VideoGenerationResult", back_populates="video", cascade="all, delete-orphan"
    )


class VideoCodes(Base):
    __tablename__ = "video_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    video_id: Mapped[int] = mapped_column(ForeignKey("videos.id"), nullable=False)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    video: Mapped["Videos"] = relationship("Videos", back_populates="codes")


class ManimConfig(Base):
    __tablename__ = "manim_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    scene_name: Mapped[str] = mapped_column(String, nullable=False)
    resolution: Mapped[str] = mapped_column(String, default="1920x1080", nullable=False)
    frame_rate: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    duration: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    output_format: Mapped[str] = mapped_column(String, default="mp4", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    user: Mapped["User"] = relationship("User", back_populates="manim_configs")


class ManimRenderRequest(Base):
    __tablename__ = "manim_render_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    config_id: Mapped[int] = mapped_column(
        ForeignKey("manim_configs.id"), nullable=False
    )
    script: Mapped[str] = mapped_column(Text, nullable=False)
    output_path: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[RenderStatus] = mapped_column(
        Enum(RenderStatus), default=RenderStatus.PENDING, nullable=False
    )
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    progress_percentage: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="manim_render_requests")
    config: Mapped["ManimConfig"] = relationship("ManimConfig")


class VideoGenerationRequest(Base):
    __tablename__ = "video_generation_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    video_id: Mapped[str] = mapped_column(
        String, nullable=False, unique=True, index=True
    )  # UUID from generator
    original_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    scene_file: Mapped[str] = mapped_column(String, default="scene.py", nullable=False)
    scene_name: Mapped[str] = mapped_column(
        String, default="GeneratedScene", nullable=False
    )
    extra_packages: Mapped[list[str]] = mapped_column(JSON, nullable=True, default=list)
    max_lint_batch_rounds: Mapped[int] = mapped_column(
        Integer, default=2, nullable=False
    )
    max_post_runtime_lint_rounds: Mapped[int] = mapped_column(
        Integer, default=2, nullable=False
    )
    max_runtime_fix_attempts: Mapped[int] = mapped_column(
        Integer, default=2, nullable=False
    )
    status: Mapped[GenerationStatus] = mapped_column(
        Enum(GenerationStatus), default=GenerationStatus.PENDING, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship(
        "User", back_populates="video_generation_requests"
    )
    generation_result: Mapped["VideoGenerationResult"] = relationship(
        "VideoGenerationResult",
        back_populates="request",
        cascade="all, delete-orphan",
        uselist=False,
    )


class VideoGenerationResult(Base):
    __tablename__ = "video_generation_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    request_id: Mapped[int] = mapped_column(
        ForeignKey("video_generation_requests.id"), nullable=False, unique=True
    )
    video_id: Mapped[int] = mapped_column(
        ForeignKey("videos.id"), nullable=True
    )  # Links to final video record
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    video_path: Mapped[str] = mapped_column(
        String, nullable=True
    )  # Generated video path
    upgraded_prompt: Mapped[dict] = mapped_column(
        JSON, nullable=True
    )  # UpgradedPrompt data
    generated_code: Mapped[str] = mapped_column(Text, nullable=True)
    lint_issues: Mapped[list[dict]] = mapped_column(
        JSON, nullable=True, default=list
    )  # LintIssue data
    runtime_errors: Mapped[list[str]] = mapped_column(JSON, nullable=True, default=list)
    logs: Mapped[dict] = mapped_column(JSON, nullable=True, default=dict)
    error_message: Mapped[str] = mapped_column(
        Text, nullable=True
    )  # General error message
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    request: Mapped["VideoGenerationRequest"] = relationship(
        "VideoGenerationRequest", back_populates="generation_result"
    )
    video: Mapped["Videos"] = relationship(
        "Videos", back_populates="generation_results"
    )
