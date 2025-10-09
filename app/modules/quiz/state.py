"""In-memory quiz room manager with basic gameplay loop.

Rooms are kept in-process only (MVP). Each room supports up to 2 players and
can also run as single-player. Fastest-finger scoring: the first correct
answer for a question gets 1 point; no penalties otherwise. Each question has
an expiration based on the room's spec.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional
from uuid import uuid4

from fastapi import WebSocket

from app.modules.quiz.models import (
    PlayerSummary,
    QuizQuestion,
    QuizSpec,
    RoomState,
    RoomStatus,
)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: Optional[datetime]) -> Optional[str]:
    if not dt:
        return None
    return dt.isoformat().replace("+00:00", "Z")


def _short_id() -> str:
    # 6-char slice from uuid4
    return uuid4().hex[:6]


@dataclass
class Player:
    id: str
    name: str
    score: int = 0
    joined_at: datetime = field(default_factory=_now_utc)
    ready: bool = False


@dataclass
class Room:
    id: str
    spec: QuizSpec
    host_id: str
    created_at: datetime = field(default_factory=_now_utc)
    status: RoomStatus = RoomStatus.WAITING
    players: Dict[str, Player] = field(default_factory=dict)
    questions: list[QuizQuestion] = field(default_factory=list)
    current_question_index: int = 0
    question_expires_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    last_activity: datetime = field(default_factory=_now_utc)
    # runtime
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)
    _runner_task: Optional[asyncio.Task] = field(default=None, repr=False)
    _question_open: bool = field(default=False, repr=False)
    _answered: set[str] = field(default_factory=set, repr=False)

    def to_state(self) -> RoomState:
        return RoomState(
            id=self.id,
            spec=self.spec,
            status=self.status,
            host_id=self.host_id,
            players=[
                PlayerSummary(id=p.id, name=p.name, score=p.score, ready=p.ready)
                for p in self.players.values()
            ],
            current_question_index=self.current_question_index,
            total_questions=len(self.questions),
            question_expires_at=_iso(self.question_expires_at),
            created_at=_iso(self.created_at) or "",
            started_at=_iso(self.started_at),
            ended_at=_iso(self.ended_at),
            ready_count=sum(1 for p in self.players.values() if p.ready),
        )


class Connections:
    """Tracks active WS connections per room with player identity."""

    def __init__(self) -> None:
        self._by_room: dict[str, dict[WebSocket, str]] = {}

    async def join(self, room_id: str, player_id: str, ws: WebSocket) -> None:
        await ws.accept()
        self._by_room.setdefault(room_id, {})[ws] = player_id

    def leave(self, room_id: str, ws: WebSocket) -> None:
        room_map = self._by_room.get(room_id)
        if not room_map:
            return
        room_map.pop(ws, None)
        if not room_map:
            self._by_room.pop(room_id, None)

    async def broadcast(self, room_id: str, payload: dict) -> None:
        room_map = self._by_room.get(room_id, {})
        dead: list[WebSocket] = []
        data = json.dumps(payload, ensure_ascii=False)
        for ws in list(room_map.keys()):
            try:
                await ws.send_text(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.leave(room_id, ws)

    def count(self, room_id: str) -> int:
        return len(self._by_room.get(room_id, {}))


class QuizManager:
    def __init__(self) -> None:
        self.rooms: dict[str, Room] = {}
        self.conns = Connections()
        self._cleanup_task: Optional[asyncio.Task] = None
        self._idle_seconds: int = 600
        self._sweep_interval: int = 60

    # Room lifecycle -----------------------------------------------------
    def create_room(self, *, host_name: str, spec: QuizSpec) -> tuple[Room, Player]:
        room_id = _short_id()
        host_id = _short_id()
        host = Player(id=host_id, name=host_name)
        room = Room(id=room_id, spec=spec, host_id=host_id)
        room.players[host_id] = host
        self.rooms[room_id] = room
        room.last_activity = _now_utc()
        return room, host

    def get_room(self, room_id: str) -> Optional[Room]:
        return self.rooms.get(room_id)

    def join_room(self, room_id: str, *, name: str) -> Player:
        room = self.rooms.get(room_id)
        if not room:
            raise ValueError("room_not_found")
        if len(room.players) >= 2:
            raise ValueError("room_full")
        pid = _short_id()
        p = Player(id=pid, name=name)
        room.players[pid] = p
        room.last_activity = _now_utc()
        return p

    async def start_room(self, room_id: str, *, questions: list[QuizQuestion]) -> None:
        room = self.rooms.get(room_id)
        if not room:
            raise ValueError("room_not_found")
        if room.status != RoomStatus.WAITING:
            return
        room.questions = list(questions)
        room.current_question_index = 0
        room.started_at = _now_utc()
        room.status = RoomStatus.IN_PROGRESS
        room.last_activity = _now_utc()
        await self._ensure_runner(room)

    async def _ensure_runner(self, room: Room) -> None:
        if room._runner_task and not room._runner_task.done():
            return
        room._runner_task = asyncio.create_task(self._run_room(room))

    # Gameplay loop ------------------------------------------------------
    async def _run_room(self, room: Room) -> None:
        try:
            while True:
                async with room._lock:
                    if room.current_question_index >= len(room.questions):
                        await self._end_room(room)
                        return
                    # announce question
                    q = room.questions[room.current_question_index]
                    expires_at = _now_utc() + timedelta(
                        seconds=room.spec.time_per_question_sec
                    )
                    room.question_expires_at = expires_at
                    room._question_open = True
                    room._answered.clear()
                await self.conns.broadcast(
                    room.id,
                    {
                        "type": "question",
                        "data": {
                            "index": room.current_question_index,
                            "question": q.question,
                            "choices": q.choices,
                            "expires_at": _iso(expires_at),
                        },
                    },
                )
                room.last_activity = _now_utc()

                # wait for expiry or early finish flag
                while True:
                    await asyncio.sleep(0.1)
                    if not room._question_open:
                        break
                    if (
                        room.question_expires_at
                        and _now_utc() >= room.question_expires_at
                    ):
                        # time out
                        async with room._lock:
                            room._question_open = False
                        # broadcast timeout result
                        await self.conns.broadcast(
                            room.id,
                            {
                                "type": "answer_result",
                                "data": {
                                    "index": room.current_question_index,
                                    "result": "timeout",
                                },
                            },
                        )
                        room.last_activity = _now_utc()
                        break

                # proceed to next question after brief pause
                await asyncio.sleep(0.5)
                async with room._lock:
                    room.current_question_index += 1
                    await self.conns.broadcast(
                        room.id,
                        {"type": "room_state", "data": room.to_state().model_dump()},
                    )
                    room.last_activity = _now_utc()
        except asyncio.CancelledError:
            return
        except Exception:
            # Best-effort end
            await self._end_room(room)

    async def _end_room(self, room: Room) -> None:
        room.status = RoomStatus.ENDED
        room.ended_at = _now_utc()
        room.last_activity = _now_utc()
        await self.conns.broadcast(
            room.id,
            {
                "type": "end",
                "data": {
                    "state": room.to_state().model_dump(),
                    "scoreboard": [
                        {
                            "player_id": p.id,
                            "name": p.name,
                            "score": p.score,
                        }
                        for p in room.players.values()
                    ],
                },
            },
        )

    # Incoming answers ---------------------------------------------------
    async def submit_answer(
        self, room_id: str, *, player_id: str, answer_index: int
    ) -> dict:
        room = self.rooms.get(room_id)
        if not room:
            raise ValueError("room_not_found")
        async with room._lock:
            if room.status != RoomStatus.IN_PROGRESS or not room._question_open:
                return {"status": "ignored"}
            q = room.questions[room.current_question_index]
            # ignore duplicate answers for the same question
            if player_id in room._answered:
                return {"status": "ignored"}
            room._answered.add(player_id)
            correct = int(answer_index) == int(q.correct_index)
            if correct:
                # first correct closes the question and awards 1 point
                room._question_open = False
                player = room.players.get(player_id)
                if player:
                    player.score += 1
                await self.conns.broadcast(
                    room.id,
                    {
                        "type": "answer_result",
                        "data": {
                            "index": room.current_question_index,
                            "player_id": player_id,
                            "correct": True,
                            "correct_index": q.correct_index,
                            "scoreboard": [
                                {
                                    "player_id": p.id,
                                    "name": p.name,
                                    "score": p.score,
                                }
                                for p in room.players.values()
                            ],
                        },
                    },
                )
                room.last_activity = _now_utc()
                return {"status": "ok", "correct": True}
            else:
                # wrong answers do not end question or penalize
                await self.conns.broadcast(
                    room.id,
                    {
                        "type": "answer_result",
                        "data": {
                            "index": room.current_question_index,
                            "player_id": player_id,
                            "correct": False,
                        },
                    },
                )
                # If all players have answered, close and reveal answer
                if len(room._answered) >= len(room.players):
                    room._question_open = False
                    await self.conns.broadcast(
                        room.id,
                        {
                            "type": "answer_result",
                            "data": {
                                "index": room.current_question_index,
                                "result": "all_answered",
                                "correct_index": q.correct_index,
                                "scoreboard": [
                                    {
                                        "player_id": p.id,
                                        "name": p.name,
                                        "score": p.score,
                                    }
                                    for p in room.players.values()
                                ],
                            },
                        },
                    )
                room.last_activity = _now_utc()
                return {"status": "ok", "correct": False}

    # Ready state --------------------------------------------------------
    async def set_ready(
        self, room_id: str, *, player_id: str, ready: bool
    ) -> RoomState:
        room = self.rooms.get(room_id)
        if not room:
            raise ValueError("room_not_found")
        async with room._lock:
            p = room.players.get(player_id)
            if not p:
                raise ValueError("player_not_found")
            p.ready = bool(ready)
            room.last_activity = _now_utc()
            state = room.to_state()
        # Broadcast updated state
        await self.conns.broadcast(
            room_id, {"type": "room_state", "data": state.model_dump()}
        )
        # Check for auto-start
        await self._maybe_auto_start(room_id)
        return self.rooms[room_id].to_state()  # type: ignore

    async def _maybe_auto_start(self, room_id: str) -> None:
        room = self.rooms.get(room_id)
        if not room:
            return
        async with room._lock:
            if room.status != RoomStatus.WAITING:
                return
            players = list(room.players.values())
            if not players:
                return
            if not all(p.ready for p in players):
                return
            existing = list(room.questions)
        # All ready: use existing questions if present, else generate
        try:
            from app.modules.quiz.models import QuizMode
            from app.modules.quiz.generator import (
                generate_math_questions,
                generate_ai_questions,
            )

            questions = existing
            if not questions:
                if room.spec.mode == QuizMode.MATH:
                    questions = generate_math_questions(
                        num_questions=room.spec.num_questions,
                        min_value=room.spec.min_value,
                        max_value=room.spec.max_value,
                        ops=room.spec.math_ops,
                        division_integer_only=room.spec.division_integer_only,
                    )
                else:
                    topic = room.spec.topic or "General knowledge"
                    questions = await generate_ai_questions(
                        topic, n=room.spec.num_questions
                    )
                    if not questions:
                        questions = []
            if not questions:
                # fallback single question
                questions = [
                    QuizQuestion(
                        question="Ready check: continue?",
                        choices=["Yes", "No", "Maybe", "Skip"],
                        correct_index=0,
                    )
                ]
            await self.start_room(room_id, questions=questions)
        except Exception:
            # Ignore errors silently for MVP
            return

    # Cleanup loop -------------------------------------------------------
    def start(self, *, idle_seconds: int = 600, sweep_interval: int = 60) -> None:
        self._idle_seconds = max(60, int(idle_seconds))
        self._sweep_interval = max(5, int(sweep_interval))
        if self._cleanup_task and not self._cleanup_task.done():
            return
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop(self) -> None:
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except Exception:
                pass
        self._cleanup_task = None

    async def _cleanup_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(self._sweep_interval)
                now = _now_utc()
                to_delete: list[str] = []
                for room_id, room in list(self.rooms.items()):
                    idle = (
                        now - (room.last_activity or room.created_at)
                    ).total_seconds()
                    connections = self.conns.count(room_id)
                    should_delete = False
                    if room.status == RoomStatus.ENDED and room.ended_at:
                        if (now - room.ended_at).total_seconds() > self._idle_seconds:
                            should_delete = True
                    elif idle > self._idle_seconds and connections == 0:
                        should_delete = True
                    if should_delete:
                        # Cancel runner if any
                        if room._runner_task and not room._runner_task.done():
                            room._runner_task.cancel()
                        to_delete.append(room_id)
                for rid in to_delete:
                    self.rooms.pop(rid, None)
        except asyncio.CancelledError:
            return


# Singleton manager used by API/WS layer
quiz_manager = QuizManager()
