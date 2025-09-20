"""Pydantic models for Quiz (MCQ) gameplay and configuration.

This mirrors the style of the flashcards module: simple Pydantic schemas
used by API handlers and the in-memory quiz engine. DB models live under
app.core.db.schemas.quiz (not required for runtime in-memory MVP).
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class QuizMode(str, Enum):
    TOPIC_AI = "topic_ai"
    MATH = "math"


class QuizQuestion(BaseModel):
    """A single multiple-choice question."""

    question: str
    choices: list[str] = Field(default_factory=list)
    correct_index: int


class QuizSpec(BaseModel):
    """Room configuration and generation parameters."""

    mode: QuizMode
    # Topic-based AI generation
    topic: Optional[str] = None

    # Count and timing
    num_questions: int = 10
    time_per_question_sec: int = 30

    # Math configuration
    math_ops: list[str] = Field(
        default_factory=lambda: ["add", "div"],
        description="Allowed operations for math mode: add|div",
    )
    min_value: int = 1
    max_value: int = 99
    division_integer_only: bool = True


class PlayerSummary(BaseModel):
    id: str
    name: str
    score: int = 0
    ready: bool = False


class RoomStatus(str, Enum):
    WAITING = "waiting"
    IN_PROGRESS = "in_progress"
    ENDED = "ended"


class RoomState(BaseModel):
    id: str
    spec: QuizSpec
    status: RoomStatus
    host_id: str
    players: list[PlayerSummary] = Field(default_factory=list)
    current_question_index: int = 0
    total_questions: int = 0
    question_expires_at: Optional[str] = None  # ISO-8601 timestamp
    created_at: str
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    ready_count: int = 0
    max_players: int = 2


class WSOutbound(BaseModel):
    """Typed envelope for websocket outgoing messages."""

    type: str
    data: dict = Field(default_factory=dict)
