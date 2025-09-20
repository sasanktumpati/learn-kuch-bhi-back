from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Optional

from app.modules.quiz.models import QuizMode, QuizSpec, RoomState


class CreateRoomRequest(BaseModel):
    host_name: str = Field(..., description="Display name of room creator")
    mode: QuizMode
    topic: Optional[str] = None
    num_questions: int = 10
    time_per_question_sec: int = 30
    # Math settings
    math_ops: list[str] = Field(default_factory=lambda: ["add", "div"])
    min_value: int = 1
    max_value: int = 99
    division_integer_only: bool = True


class CreateRoomResponse(BaseModel):
    room_id: str
    player_id: str
    ws_url: str
    state: RoomState


class JoinRoomRequest(BaseModel):
    display_name: str


class JoinRoomResponse(BaseModel):
    player_id: str
    ws_url: str
    state: RoomState


class StartRoomResponse(BaseModel):
    ok: bool
    state: RoomState


class RoomStateResponse(BaseModel):
    state: RoomState


class RoomListItem(BaseModel):
    room_id: str
    mode: QuizMode
    status: str
    players: int
    max_players: int = 2
    ready_count: int
    host_id: str
    host_name: str | None = None
    topic: str | None = None
    created_at: str
    started_at: str | None = None
    ended_at: str | None = None
