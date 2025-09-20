from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect

from app.core.config import settings
from app.apis.quiz.schemas import (
    CreateRoomRequest,
    CreateRoomResponse,
    JoinRoomRequest,
    JoinRoomResponse,
    RoomStateResponse,
    StartRoomResponse,
    RoomListItem,
)
from app.modules.quiz.models import QuizMode, QuizSpec
from app.modules.quiz.state import quiz_manager
from app.modules.quiz.generator import generate_math_questions, generate_ai_questions


router = APIRouter()


def _build_spec(req: CreateRoomRequest) -> QuizSpec:
    return QuizSpec(
        mode=req.mode,
        topic=req.topic,
        num_questions=max(1, int(req.num_questions or 10)),
        time_per_question_sec=max(5, int(req.time_per_question_sec or 30)),
        math_ops=req.math_ops or ["add", "div"],
        min_value=int(req.min_value or 1),
        max_value=int(req.max_value or 99),
        division_integer_only=bool(req.division_integer_only),
    )


@router.post(
    f"/{settings.app.version}/quiz/rooms",
    response_model=CreateRoomResponse,
    tags=["quiz"],
)
async def create_room(req: CreateRoomRequest) -> CreateRoomResponse:
    spec = _build_spec(req)
    room, host = quiz_manager.create_room(host_name=req.host_name, spec=spec)
    # Pre-generate questions immediately (AI or Math)
    try:
        if spec.mode == QuizMode.MATH:
            room.questions = generate_math_questions(
                num_questions=spec.num_questions,
                min_value=spec.min_value,
                max_value=spec.max_value,
                ops=spec.math_ops,
                division_integer_only=spec.division_integer_only,
            )
        else:
            topic = spec.topic or "General knowledge"
            room.questions = await generate_ai_questions(topic, n=spec.num_questions)
    except Exception:
        # Leave room without questions; frontend can still start later
        room.questions = room.questions or []
    ws_url = f"/{settings.app.version}/quiz/ws/{room.id}?player_id={host.id}"
    return CreateRoomResponse(
        room_id=room.id, player_id=host.id, ws_url=ws_url, state=room.to_state()
    )


@router.post(
    f"/{settings.app.version}/quiz/rooms/{{room_id}}/join",
    response_model=JoinRoomResponse,
    tags=["quiz"],
)
async def join_room(room_id: str, req: JoinRoomRequest) -> JoinRoomResponse:
    try:
        player = quiz_manager.join_room(room_id, name=req.display_name)
    except ValueError as e:
        msg = str(e)
        if msg == "room_not_found":
            raise HTTPException(status_code=404, detail="Room not found")
        if msg == "room_full":
            raise HTTPException(status_code=409, detail="Room is full")
        raise
    room = quiz_manager.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    ws_url = f"/{settings.app.version}/quiz/ws/{room.id}?player_id={player.id}"
    return JoinRoomResponse(player_id=player.id, ws_url=ws_url, state=room.to_state())


@router.get(
    f"/{settings.app.version}/quiz/rooms/{{room_id}}",
    response_model=RoomStateResponse,
    tags=["quiz"],
)
async def get_room_state(room_id: str) -> RoomStateResponse:
    room = quiz_manager.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    return RoomStateResponse(state=room.to_state())


@router.get(
    f"/{settings.app.version}/quiz/rooms",
    response_model=list[RoomListItem],
    tags=["quiz"],
)
async def list_rooms() -> list[RoomListItem]:
    items: list[RoomListItem] = []
    for room in quiz_manager.rooms.values():
        players = list(room.players.values())
        host = room.players.get(room.host_id)
        items.append(
            RoomListItem(
                room_id=room.id,
                mode=room.spec.mode,
                status=room.status.value,
                players=len(players),
                max_players=2,
                ready_count=sum(1 for p in players if p.ready),
                host_id=room.host_id,
                host_name=(host.name if host else None),
                topic=room.spec.topic,
                created_at=(room.created_at.isoformat().replace("+00:00", "Z")),
                started_at=(
                    room.started_at.isoformat().replace("+00:00", "Z")
                    if room.started_at
                    else None
                ),
                ended_at=(
                    room.ended_at.isoformat().replace("+00:00", "Z")
                    if room.ended_at
                    else None
                ),
            )
        )

    # Sort: waiting first, newest first
    def _sort_key(it: RoomListItem):
        status_rank = (
            0 if it.status == "waiting" else (1 if it.status == "in_progress" else 2)
        )
        return (status_rank, it.created_at)

    return sorted(items, key=_sort_key)


@router.post(
    f"/{settings.app.version}/quiz/rooms/{{room_id}}/start",
    response_model=StartRoomResponse,
    tags=["quiz"],
)
async def start_room(room_id: str) -> StartRoomResponse:
    room = quiz_manager.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    # Only host can start (MVP, but no auth): if 2 players exist, still allow anyone to call
    try:
        questions = list(room.questions)
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
                    # Fallback: one trivial question to avoid hanging room
                    from app.modules.quiz.models import QuizQuestion as QQ

                    questions = [
                        QQ(
                            question=f"Which topic are we studying?",
                            choices=[topic, "Math", "Science", "History"],
                            correct_index=0,
                        )
                    ]
        await quiz_manager.start_room(room_id, questions=questions)
        room = quiz_manager.get_room(room_id)
        return StartRoomResponse(ok=True, state=room.to_state() if room else None)  # type: ignore
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    f"/{settings.app.version}/quiz/rooms/{{room_id}}/players/{{player_id}}/ready",
    response_model=RoomStateResponse,
    tags=["quiz"],
)
async def set_ready(
    room_id: str, player_id: str, ready: bool = True
) -> RoomStateResponse:
    try:
        state = await quiz_manager.set_ready(room_id, player_id=player_id, ready=ready)
        return RoomStateResponse(state=state)
    except ValueError as e:
        msg = str(e)
        if msg == "room_not_found":
            raise HTTPException(status_code=404, detail="Room not found")
        if msg == "player_not_found":
            raise HTTPException(status_code=404, detail="Player not found")
        raise


@router.websocket(f"/{settings.app.version}/quiz/ws/{{room_id}}")
async def ws_room(websocket: WebSocket, room_id: str) -> None:
    player_id = websocket.query_params.get("player_id")
    if not player_id:
        await websocket.close(code=4401)
        return
    room = quiz_manager.get_room(room_id)
    if not room or player_id not in room.players:
        await websocket.close(code=4404)
        return

    await quiz_manager.conns.join(room_id, player_id, websocket)
    # Send initial state
    try:
        await websocket.send_json(
            {"type": "room_state", "data": room.to_state().model_dump()}
        )
    except Exception:
        pass

    try:
        while True:
            msg = await websocket.receive_json()
            if not isinstance(msg, dict):
                continue
            mtype = msg.get("type")
            if mtype == "answer":
                ans = msg.get("answer_index")
                if ans is None:
                    continue
                try:
                    await quiz_manager.submit_answer(
                        room_id, player_id=player_id, answer_index=int(ans)
                    )
                except Exception:
                    # Ignore malformed during MVP
                    pass
            elif mtype == "ready":
                val = bool(msg.get("ready", True))
                try:
                    await quiz_manager.set_ready(
                        room_id, player_id=player_id, ready=val
                    )
                except Exception:
                    pass
            else:
                # No-op; ignore unknown types
                continue
    except WebSocketDisconnect:
        quiz_manager.conns.leave(room_id, websocket)
    except Exception:
        quiz_manager.conns.leave(room_id, websocket)
