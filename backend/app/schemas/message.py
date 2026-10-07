from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.models.enums import MessageKind, MessageStatus

MAX_MESSAGE_LENGTH = 4000

MessageBody = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_MESSAGE_LENGTH)]
ClientId = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_\-:]{8,64}$")]


class MessageOut(BaseModel):
    id: int
    conversation_id: int
    client_id: str | None
    kind: MessageKind
    text: str  # body, or viewer-relative text for system messages
    sender_id: int | None
    sender_name: str | None  # null for my own and system messages
    sender_avatar_color: str | None
    sender_avatar_url: str | None
    created_at: datetime
    status: MessageStatus | None  # only for my own text messages


class MessagePage(BaseModel):
    items: list[MessageOut]  # oldest first
    next_cursor: int | None  # pass as `before` to load older messages; null when there are none


class SendMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_id: ClientId
    body: MessageBody


class ReadRequest(BaseModel):
    up_to_message_id: int
