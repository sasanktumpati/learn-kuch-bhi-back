from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
    JSON,
    Enum,
    UniqueConstraint,
    text as sa_text,
)
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
    __table_args__ = ()

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        server_default=sa_text("'[]'"),
    )  # JSON array of tags
    # Link to multi-generation run and subtopic identification (optional)
    multi_result_id: Mapped[int | None] = mapped_column(
        ForeignKey("multi_flashcards_results.id"), nullable=True, index=True
    )
    subtopic_id: Mapped[int | None] = mapped_column(
        ForeignKey("fc_subtopics.id"), nullable=True, index=True
    )
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
        index=True,
    )

    user: Mapped["User"] = relationship("User", back_populates="flashcard_sets")
    flashcards: Mapped[list["Flashcard"]] = relationship(
        "Flashcard", back_populates="flashcard_set", cascade="all, delete-orphan"
    )
    multi_result: Mapped[Optional["MultiFlashcardsResult"]] = relationship(
        "MultiFlashcardsResult", back_populates="flashcard_sets"
    )
    subtopic: Mapped[Optional["Subtopic"]] = relationship(
        "Subtopic", back_populates="flashcard_sets"
    )


class Flashcard(Base):
    __tablename__ = "flashcards"
    __table_args__ = (
        UniqueConstraint(
            "flashcard_set_id",
            "order_index",
            name="uq_flashcard_set_order",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    flashcard_set_id: Mapped[int] = mapped_column(
        ForeignKey("flashcard_sets.id"), nullable=False, index=True
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
        index=True,
    )

    flashcard_set: Mapped["FlashcardSet"] = relationship(
        "FlashcardSet", back_populates="flashcards"
    )


class MultiFlashcardsResult(Base):
    __tablename__ = "multi_flashcards_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    # Inline outline JSON (replaces separate TopicOutline table)
    outline: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
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
        index=True,
    )
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True, index=True)

    user: Mapped["User"] = relationship(
        "User", back_populates="multi_flashcards_results"
    )
    flashcard_sets: Mapped[list["FlashcardSet"]] = relationship(
        "FlashcardSet", back_populates="multi_result"
    )
    topics: Mapped[list["Topic"]] = relationship(
        "Topic", back_populates="multi_result", cascade="all, delete-orphan"
    )


class Topic(Base):
    __tablename__ = "fc_topics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    multi_result_id: Mapped[int] = mapped_column(
        ForeignKey("multi_flashcards_results.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), index=True
    )

    multi_result: Mapped["MultiFlashcardsResult"] = relationship(
        "MultiFlashcardsResult", back_populates="topics"
    )
    subtopics: Mapped[list["Subtopic"]] = relationship(
        "Subtopic", back_populates="topic", cascade="all, delete-orphan"
    )


class Subtopic(Base):
    __tablename__ = "fc_subtopics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("fc_topics.id"), index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), index=True
    )

    topic: Mapped["Topic"] = relationship("Topic", back_populates="subtopics")
    flashcard_sets: Mapped[list["FlashcardSet"]] = relationship(
        "FlashcardSet", back_populates="subtopic"
    )


__all__ = [
    "GenerationStatus",
    "FlashcardSet",
    "Flashcard",
    "MultiFlashcardsResult",
    "Topic",
    "Subtopic",
]
