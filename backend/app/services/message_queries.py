"""Shared message-visibility rules (PLAN 1.6, 7.1, 7.2). Every query that shows a member
messages - history, unread count, last-message preview, chat-list ordering - goes through
`visible_to`, so all of them respect the member's history range and their blocks."""

from collections import defaultdict
from collections.abc import Sequence

from sqlalchemy import ColumnElement, Select, and_, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Block, ConversationMember, Message, MessageReceipt, User, UserSettings
from app.models import Conversation
from app.models.enums import MessageKind, MessageStatus


def not_from_blocked(viewer_id: int) -> ColumnElement[bool]:
    """Excludes messages (including system lines, e.g. renames) from users the viewer blocked,
    sent after the block. Signal hides a blocked person's messages *and* their changes to a
    shared group from the blocker (PLAN 7.2)."""
    return ~exists().where(
        Block.blocker_id == viewer_id,
        Block.blocked_id == Message.sender_id,
        Block.created_at <= Message.created_at,
    )


def visible_to(member: ConversationMember) -> ColumnElement[bool]:
    """Messages of the member's conversation inside their history range, minus messages from
    users they blocked that were sent after the block."""
    in_range = and_(Message.conversation_id == member.conversation_id, Message.id > member.history_start_id)
    if member.history_end_id is not None:
        in_range = and_(in_range, Message.id <= member.history_end_id)
    return and_(in_range, not_from_blocked(member.user_id))


async def unread_count(session: AsyncSession, member: ConversationMember) -> int:
    query = select(func.count()).where(
        visible_to(member),
        Message.id > member.last_read_message_id,
        Message.kind == MessageKind.TEXT,
        or_(Message.sender_id.is_(None), Message.sender_id != member.user_id),
    )
    return (await session.execute(query)).scalar_one()


async def last_visible_message(session: AsyncSession, member: ConversationMember) -> Message | None:
    """The member's last-message preview; its created_at is their chat-list sort key."""
    query = select(Message).where(visible_to(member)).order_by(Message.id.desc()).limit(1)
    return (await session.execute(query)).scalar_one_or_none()


def aggregate_status(receipts: Sequence[MessageReceipt]) -> MessageStatus:
    """Status the sender sees: read only when every recipient read it, delivered when
    everyone has it, otherwise sent (also when there are no recipients, e.g. blocked)."""
    if not receipts or any(receipt.delivered_at is None for receipt in receipts):
        return MessageStatus.SENT
    if all(receipt.read_at is not None for receipt in receipts):
        return MessageStatus.READ
    return MessageStatus.DELIVERED


def current_member_receipts(message_ids: Sequence[int]) -> Select[MessageReceipt]:
    """Receipts of these messages from people who are *still* active members. Someone who
    was removed or left no longer counts, so they can't hold a sender's tick back forever."""
    return (
        select(MessageReceipt)
        .join(Message, Message.id == MessageReceipt.message_id)
        .join(
            ConversationMember,
            and_(
                ConversationMember.conversation_id == Message.conversation_id,
                ConversationMember.user_id == MessageReceipt.user_id,
                ConversationMember.left_at.is_(None),
            ),
        )
        .where(MessageReceipt.message_id.in_(message_ids))
    )


async def statuses_for(session: AsyncSession, viewer: User, message_ids: Sequence[int]) -> dict[int, MessageStatus]:
    """The ticks the sender sees for their own messages (PLAN 1.8). Capped at delivered when
    the viewer has read receipts off (PLAN 7.4)."""
    if not message_ids:
        return {}
    by_message: defaultdict[int, list[MessageReceipt]] = defaultdict(list)
    for receipt in (await session.execute(current_member_receipts(message_ids))).scalars():
        by_message[receipt.message_id].append(receipt)
    settings = await session.get(UserSettings, viewer.id)
    receipts_on = settings is None or settings.read_receipts_enabled

    statuses: dict[int, MessageStatus] = {}
    for message_id in message_ids:
        status = aggregate_status(by_message[message_id])
        if status is MessageStatus.READ and not receipts_on:
            status = MessageStatus.DELIVERED
        statuses[message_id] = status
    return statuses


NAME_EVENTS = ("group_created", "group_renamed")
PHOTO_EVENTS = ("group_avatar_changed",)


async def group_appearance(session: AsyncSession, viewer_id: int, conversation: Conversation) -> tuple[str, str | None]:
    """The group's name and photo as this viewer may see them. If the latest rename / photo
    change came from someone the viewer blocked, they keep seeing the previous name and the
    default photo (the previous photo file is deleted on change, so it can't be shown)."""
    name, photo = conversation.name or "Group", conversation.avatar_url
    if await session.scalar(select(Block.blocked_id).where(Block.blocker_id == viewer_id).limit(1)) is None:
        return name, photo  # fast path: the viewer blocked nobody

    def events(kinds: tuple[str, ...]) -> Select[Message]:
        return (
            select(Message)
            .where(Message.conversation_id == conversation.id, Message.kind == MessageKind.SYSTEM, Message.body.in_(kinds))
            .order_by(Message.id.desc())
            .limit(1)
        )

    latest_name, allowed_name = (
        await session.scalar(events(NAME_EVENTS)),
        await session.scalar(events(NAME_EVENTS).where(not_from_blocked(viewer_id))),
    )
    if latest_name is not None and latest_name is not allowed_name:
        name = str((allowed_name.system_data or {}).get("name", "Group")) if allowed_name else "Group"

    latest_photo, allowed_photo = (
        await session.scalar(events(PHOTO_EVENTS)),
        await session.scalar(events(PHOTO_EVENTS).where(not_from_blocked(viewer_id))),
    )
    if latest_photo is not None and latest_photo is not allowed_photo:
        photo = None
    return name, photo
