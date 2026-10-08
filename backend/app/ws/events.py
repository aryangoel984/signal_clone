"""The WebSocket contract (PLAN section 3): every frame is {"type": ..., "payload": {...}}."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

from app.models.enums import MessageStatus
from app.schemas.message import MessageOut


def envelope(event_type: str, payload: BaseModel | dict[str, Any]) -> dict[str, Any]:
    body = payload.model_dump(mode="json") if isinstance(payload, BaseModel) else payload
    return {"type": event_type, "payload": body}


class MessageNew(BaseModel):
    conversation_id: int
    message: MessageOut  # worded for the receiving user


class StatusUpdate(BaseModel):
    message_id: int
    status: MessageStatus


class MessageStatusChanged(BaseModel):
    conversation_id: int
    updates: list[StatusUpdate]


class Typing(BaseModel):
    conversation_id: int
    user_id: int


class GroupUpdated(BaseModel):
    conversation_id: int
    change: str  # created | renamed | avatar_changed | members_added | member_removed | member_left | role_changed
    actor_id: int
    target_ids: list[int]


class PresenceUpdate(BaseModel):
    user_id: int
    online: bool
    last_seen_at: datetime | None


# --- client -> server ---------------------------------------------------------------------


class TypingPayload(BaseModel):
    conversation_id: int


class ClientFrame(BaseModel):
    type: Literal["typing.start", "typing.stop", "ping"]
    payload: dict[str, Any] = {}
