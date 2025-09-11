from __future__ import annotations

from typing import TYPE_CHECKING
from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from fastapi_users_db_sqlalchemy import SQLAlchemyBaseUserTable

from app.core.db.base import Base

if TYPE_CHECKING:
    from .flashcards import FlashcardSet, MultiFlashcardsResult
    from .videos import Videos, ManimConfig, ManimRenderRequest, VideoGenerationRequest
    from .user_profile import UserProfile


class User(SQLAlchemyBaseUserTable[int], Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Relationships
    flashcard_sets: Mapped[list["FlashcardSet"]] = relationship(
        "FlashcardSet", back_populates="user", cascade="all, delete-orphan"
    )
    multi_flashcards_results: Mapped[list["MultiFlashcardsResult"]] = relationship(
        "MultiFlashcardsResult", back_populates="user", cascade="all, delete-orphan"
    )
    videos: Mapped[list["Videos"]] = relationship(
        "Videos", back_populates="user", cascade="all, delete-orphan"
    )
    manim_configs: Mapped[list["ManimConfig"]] = relationship(
        "ManimConfig", back_populates="user", cascade="all, delete-orphan"
    )
    manim_render_requests: Mapped[list["ManimRenderRequest"]] = relationship(
        "ManimRenderRequest", back_populates="user", cascade="all, delete-orphan"
    )
    video_generation_requests: Mapped[list["VideoGenerationRequest"]] = relationship(
        "VideoGenerationRequest", back_populates="user", cascade="all, delete-orphan"
    )
    profile: Mapped["UserProfile"] = relationship(
        "UserProfile",
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
    )


__all__ = ["User"]
