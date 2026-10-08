import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.core.db import Database
from app.services import auth_service
from app.ws.events import ClientFrame, TypingPayload, envelope
from app.ws.realtime import Realtime, TypingNotAllowedError

logger = logging.getLogger(__name__)

router = APIRouter()

UNAUTHORIZED_CLOSE_CODE = 4401


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = "") -> None:
    """GET /ws?token=... (browsers can't set an Authorization header on WebSockets)."""
    database: Database = websocket.app.state.db
    realtime: Realtime = websocket.app.state.realtime

    async with database.session_factory() as session:
        authenticated = await auth_service.authenticate(session, token) if token else None
    await websocket.accept()
    if authenticated is None:
        await websocket.close(code=UNAUTHORIZED_CLOSE_CODE, reason="Session expired or invalid")
        return
    user_id = authenticated[1].id

    if realtime.manager.connect(user_id, websocket):
        await realtime.went_online(user_id)
    await realtime.deliver_pending(user_id)
    try:
        while True:
            await _handle_frame(websocket, realtime, user_id, await websocket.receive_text())
    except WebSocketDisconnect:
        pass
    finally:
        if realtime.manager.disconnect(user_id, websocket):
            # Not awaited here: the handler may be cancelled while closing.
            realtime.spawn(realtime.went_offline(user_id))


async def _handle_frame(websocket: WebSocket, realtime: Realtime, user_id: int, raw: str) -> None:
    try:
        frame = ClientFrame.model_validate(json.loads(raw))
        if frame.type == "ping":
            await websocket.send_json(envelope("pong", {}))
            return
        payload = TypingPayload.model_validate(frame.payload)
        await realtime.typing(user_id, payload.conversation_id, started=frame.type == "typing.start")
    except (json.JSONDecodeError, ValidationError):
        await websocket.send_json(envelope("error", {"detail": "Invalid frame"}))
    except TypingNotAllowedError as error:
        await websocket.send_json(envelope("error", {"detail": str(error)}))
