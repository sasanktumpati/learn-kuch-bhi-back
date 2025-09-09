from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func, Enum
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


class Videos(Base):
    __tablename__ = "videos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    path: Mapped[str] = mapped_column(String, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    user: Mapped["User"] = relationship("User", back_populates="videos")
    codes: Mapped[list["VideoCodes"]] = relationship(
        "VideoCodes", back_populates="video", cascade="all, delete-orphan"
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
