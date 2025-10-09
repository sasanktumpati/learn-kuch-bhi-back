from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    JSON,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db.base import Base


class QuizRoomRecord(Base):
    __tablename__ = "quiz_rooms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    room_code: Mapped[str] = mapped_column(
        String, nullable=False, unique=True, index=True
    )
    mode: Mapped[str] = mapped_column(String, nullable=False)
    spec: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), index=True
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, index=True
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, index=True
    )

    questions: Mapped[list["QuizQuestionRecord"]] = relationship(
        "QuizQuestionRecord", back_populates="room", cascade="all, delete-orphan"
    )
    players: Mapped[list["QuizPlayerRecord"]] = relationship(
        "QuizPlayerRecord", back_populates="room", cascade="all, delete-orphan"
    )


class QuizQuestionRecord(Base):
    __tablename__ = "quiz_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("quiz_rooms.id"), index=True)
    q_index: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    choices: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    correct_index: Mapped[int] = mapped_column(Integer, nullable=False)

    room: Mapped["QuizRoomRecord"] = relationship(
        "QuizRoomRecord", back_populates="questions"
    )


class QuizPlayerRecord(Base):
    __tablename__ = "quiz_players"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("quiz_rooms.id"), index=True)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), index=True
    )

    room: Mapped["QuizRoomRecord"] = relationship(
        "QuizRoomRecord", back_populates="players"
    )
    answers: Mapped[list["QuizAnswerRecord"]] = relationship(
        "QuizAnswerRecord", back_populates="player", cascade="all, delete-orphan"
    )


class QuizAnswerRecord(Base):
    __tablename__ = "quiz_answers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("quiz_rooms.id"), index=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("quiz_players.id"), index=True)
    q_index: Mapped[int] = mapped_column(Integer, nullable=False)
    answer_index: Mapped[int] = mapped_column(Integer, nullable=False)
    correct: Mapped[bool] = mapped_column(Integer, nullable=False, default=0)
    answered_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), index=True
    )

    player: Mapped["QuizPlayerRecord"] = relationship(
        "QuizPlayerRecord", back_populates="answers"
    )


__all__ = [
    "QuizRoomRecord",
    "QuizQuestionRecord",
    "QuizPlayerRecord",
    "QuizAnswerRecord",
]
