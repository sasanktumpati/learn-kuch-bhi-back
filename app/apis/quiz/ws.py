from typing import Dict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.logging import get_logger

logger = get_logger(__name__)
ws_router = APIRouter()


class ConnectionManager:
    def __init__(self) -> None:
        self.active: Dict[str, set[WebSocket]] = {}

    async def connect(self, room: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active.setdefault(room, set()).add(websocket)
        logger.info("WS connected", extra={"room": room})

    def disconnect(self, room: str, websocket: WebSocket) -> None:
        room_set = self.active.get(room)
        if room_set and websocket in room_set:
            room_set.remove(websocket)
        logger.info("WS disconnected", extra={"room": room})

    async def broadcast(self, room: str, message: dict) -> None:
        for ws in list(self.active.get(room, set())):
            try:
                await ws.send_json(message)
            except Exception:
                # Best-effort; drop broken sockets
                self.disconnect(room, ws)


manager = ConnectionManager()


@ws_router.websocket("/rooms/{room}/live")
async def ws_live(websocket: WebSocket, room: str) -> None:
    # Minimal token validation via query parameter
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4401)
        return
    try:
        payload = verify_jwt(token)
        if payload.get("room") != room:
            await websocket.close(code=4403)
            return
    except Exception:
        await websocket.close(code=4401)
        return
    await manager.connect(room, websocket)
    try:
        while True:
            _ = await websocket.receive_text()
            # Echo placeholder for now
            await websocket.send_json({"ok": True})
    except WebSocketDisconnect:
        manager.disconnect(room, websocket)
