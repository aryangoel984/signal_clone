from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import ConversationType, MemberRole, MessageKind, MessageStatus


class LastMessage(BaseModel):
    id: int
    kind: MessageKind
    text: str  # message body, or viewer-relative text for system messages
    sender_id: int | None
    sender_name: str | None
    created_at: datetime
    status: MessageStatus | None  # only for the viewer's own text messages


class ConversationSummary(BaseModel):
    """One row of the chat list."""

    id: int
    type: ConversationType
    title: str
    avatar_url: str | None
    avatar_color: str
    other_user_id: int | None  # DMs only
    other_user_online: bool | None  # DMs only: has an open connection (bots always)
    other_user_last_seen_at: datetime | None  # DMs only
    is_contact: bool | None  # DMs only: is the other person in my contacts?
    member_count: int
    is_pinned: bool
    is_archived: bool
    muted_until: datetime | None
    can_send: bool  # False once I was removed from / left a group (history stays readable)
    unread_count: int
    last_message: LastMessage | None
    sort_at: datetime  # created_at of my last visible message (or the conversation's creation)


class MemberOut(BaseModel):
    user_id: int
    name: str
    avatar_url: str | None
    avatar_color: str
    role: MemberRole


class ConversationDetail(ConversationSummary):
    members: list[MemberOut]
    my_role: MemberRole
    groups_in_common: list[str]  # DMs only: names of groups both people are active in
    last_read_message_id: int  # my read watermark, for the "N Unread Messages" divider


class CreateDirectRequest(BaseModel):
    user_id: int


class UpdatePreferencesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_pinned: bool | None = None
    is_archived: bool | None = None
    muted_until: datetime | None = None
