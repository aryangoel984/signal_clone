"""Shared message-visibility rules (PLAN 1.6, 7.1, 7.2). Every query that shows a member
messages - history, unread count, last-message preview, chat-list ordering - goes through
`visible_to`, so all of them respect the member's history range and their blocks."""

from collections.abc import Sequence

from sqlalchemy import ColumnElement, and_, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Block, ConversationMember, Message, MessageReceipt
from app.models.enums import MessageKind, MessageStatus


def visible_to(member: ConversationMember) -> ColumnElement[bool]:
    """Messages of the member's conversation inside their history range, excluding
    messages from users they blocked that were sent after the block."""
    in_range = and_(Message.conversation_id == member.conversation_id, Message.id > member.history_start_id)
    if member.history_end_id is not None:
        in_range = and_(in_range, Message.id <= member.history_end_id)
    blocked_sender = exists().where(
        Block.blocker_id == member.user_id,
        Block.blocked_id == Message.sender_id,
        Block.created_at <= Message.created_at,
    )
    return and_(in_range, ~blocked_sender)


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
