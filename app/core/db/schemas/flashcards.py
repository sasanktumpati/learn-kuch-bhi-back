from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func, JSON, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.core.db.base import Base

if TYPE_CHECKING:
    from .auth import User


class GenerationStatus(enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class FlashcardSet(Base):
    __tablename__ = "flashcard_sets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[list[str]] = mapped_column(
        JSON, nullable=True, default=list
    )  # JSON array of tags
    original_prompt: Mapped[str] = mapped_column(
        Text, nullable=True
    )  # Store original generation prompt
    status: Mapped[GenerationStatus] = mapped_column(
        Enum(GenerationStatus), default=GenerationStatus.COMPLETED, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    user: Mapped["User"] = relationship("User", back_populates="flashcard_sets")
    flashcards: Mapped[list["Flashcard"]] = relationship(
        "Flashcard", back_populates="flashcard_set", cascade="all, delete-orphan"
    )


class Flashcard(Base):
    __tablename__ = "flashcards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    flashcard_set_id: Mapped[int] = mapped_column(
        ForeignKey("flashcard_sets.id"), nullable=False
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    order_index: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )  # For ordering flashcards
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    flashcard_set: Mapped["FlashcardSet"] = relationship(
        "FlashcardSet", back_populates="flashcards"
    )


class TopicOutline(Base):
    __tablename__ = "topic_outlines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    topics: Mapped[dict] = mapped_column(
        JSON, nullable=False
    )  # JSON object of topics structure
    original_prompt: Mapped[str] = mapped_column(
        Text, nullable=True
    )  # Store original generation prompt
    status: Mapped[GenerationStatus] = mapped_column(
        Enum(GenerationStatus), default=GenerationStatus.COMPLETED, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    user: Mapped["User"] = relationship("User", back_populates="topic_outlines")
    multi_flashcards_results: Mapped[list["MultiFlashcardsResult"]] = relationship(
        "MultiFlashcardsResult", back_populates="outline", cascade="all, delete-orphan"
    )


class MultiFlashcardsResult(Base):
    __tablename__ = "multi_flashcards_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    outline_id: Mapped[int] = mapped_column(
        ForeignKey("topic_outlines.id"), nullable=False
    )
    original_prompt: Mapped[str] = mapped_column(
        Text, nullable=True
    )  # Store original generation prompt
    concurrency_setting: Mapped[int] = mapped_column(Integer, default=6, nullable=False)
    status: Mapped[GenerationStatus] = mapped_column(
        Enum(GenerationStatus), default=GenerationStatus.PENDING, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship(
        "User", back_populates="multi_flashcards_results"
    )
    outline: Mapped["TopicOutline"] = relationship(
        "TopicOutline", back_populates="multi_flashcards_results"
    )
    subtopic_sets: Mapped[list["SubtopicFlashcardSet"]] = relationship(
        "SubtopicFlashcardSet",
        back_populates="multi_result",
        cascade="all, delete-orphan",
    )


class SubtopicFlashcardSet(Base):
    __tablename__ = "subtopic_flashcard_sets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    multi_result_id: Mapped[int] = mapped_column(
        ForeignKey("multi_flashcards_results.id"), nullable=False
    )
    flashcard_set_id: Mapped[int] = mapped_column(
        ForeignKey("flashcard_sets.id"), nullable=False
    )
    topic_name: Mapped[str] = mapped_column(String, nullable=False)
    subtopic_name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    multi_result: Mapped["MultiFlashcardsResult"] = relationship(
        "MultiFlashcardsResult", back_populates="subtopic_sets"
    )
    flashcard_set: Mapped["FlashcardSet"] = relationship("FlashcardSet")
