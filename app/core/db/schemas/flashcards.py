from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db.base import Base

if TYPE_CHECKING:
    from .auth import User


class FlashcardSet(Base):
    __tablename__ = "flashcard_sets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[str] = mapped_column(Text, nullable=True)  # JSON string of tags
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
    topics: Mapped[str] = mapped_column(Text, nullable=False)  # JSON string of topics
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    user: Mapped["User"] = relationship("User", back_populates="topic_outlines")


class MultiFlashcardsResult(Base):
    __tablename__ = "multi_flashcards_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    outline_id: Mapped[int] = mapped_column(
        ForeignKey("topic_outlines.id"), nullable=False
    )
    sets_data: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # JSON string of subtopic flashcard sets
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    user: Mapped["User"] = relationship(
        "User", back_populates="multi_flashcards_results"
    )
    outline: Mapped["TopicOutline"] = relationship("TopicOutline")
