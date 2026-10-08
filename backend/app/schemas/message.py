from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.models.enums import MessageKind, MessageStatus

MAX_MESSAGE_LENGTH = 4000

MessageBody = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_MESSAGE_LENGTH)]
ClientId = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_\-:]{8,64}$")]
# Signal's default reaction set. The picker offers only these, so the API accepts only these.
ReactionEmoji = Literal["❤️", "👍", "👎", "😂", "😮", "😢"]


class Quote(BaseModel):
    """The message a reply quotes, as the viewer sees it."""

    id: int
    sender_id: int | None
    author_name: str  # "You" for my own messages
    text: str


class ReactionOut(BaseModel):
    user_id: int
    emoji: str


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
    reply_to_id: int | None
    quote: Quote | None  # null on a reply whose original the viewer can't see ("Original message not found")
    reactions: list[ReactionOut]  # oldest first; one per user; minus users the viewer blocked


class MessagePage(BaseModel):
    items: list[MessageOut]  # oldest first
    next_cursor: int | None  # pass as `before` to load older messages; null when there are none


class SendMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_id: ClientId
    body: MessageBody
    reply_to_id: int | None = None


class ReactRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    emoji: ReactionEmoji


class ReadRequest(BaseModel):
    up_to_message_id: int


class Recipient(BaseModel):
    """One row of "Message details": a current member and what happened on their side."""

    user_id: int
    name: str
    avatar_color: str
    avatar_url: str | None
    delivered_at: datetime | None
    read_at: datetime | None  # hidden (null) when the sender has read receipts off


class MessageDetails(BaseModel):
    message_id: int
    sent_at: datetime
    recipients: list[Recipient]
