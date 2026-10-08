"""Delivery and read state (PLAN 1.6, 1.8, 7.4). Every function returns the ids of the
messages whose receipts changed, so the caller can tell their senders (message.status)."""

from sqlalchemy import ColumnElement, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.models import ConversationMember, Message, MessageReceipt, User, UserSettings
from app.services.message_queries import visible_to


async def mark_all_delivered(session: AsyncSession, user_id: int) -> list[int]:
    """Everything waiting for this user is delivered once their client is connected (or has
    loaded the chat list). Uses the partial index ix_receipts_user_undelivered."""
    return await _set_delivered(session, MessageReceipt.user_id == user_id)


async def mark_delivered(session: AsyncSession, user_ids: list[int], message_id: int) -> list[int]:
    """A message was just pushed to these users' open sockets."""
    if not user_ids:
        return []
    return await _set_delivered(session, MessageReceipt.user_id.in_(user_ids), MessageReceipt.message_id == message_id)


async def mark_read(session: AsyncSession, viewer: User, member: ConversationMember, up_to_message_id: int) -> list[int]:
    """Moves the read watermark forward (never back), clamped to the newest message the
    member can see. Delivery is always recorded; read_at only if the reader has read
    receipts on."""
    newest_visible = await session.scalar(select(func.max(Message.id)).where(visible_to(member)))
    target = min(up_to_message_id, newest_visible or 0)
    if target <= member.last_read_message_id:
        return []
    member.last_read_message_id = target

    mine = (
        MessageReceipt.user_id == viewer.id,
        MessageReceipt.message_id.in_(
            select(Message.id).where(Message.conversation_id == member.conversation_id, Message.id <= target)
        ),
    )
    # A message on screen has been delivered, whatever the read-receipt setting
    # (and the CHECK read_implies_delivered needs delivered_at before read_at).
    changed = set(await _set_delivered(session, *mine, commit=False))

    settings = await session.get(UserSettings, viewer.id)
    if settings is None or settings.read_receipts_enabled:
        unread = (*mine, MessageReceipt.read_at.is_(None))
        changed.update((await session.execute(select(MessageReceipt.message_id).where(*unread))).scalars())
        await session.execute(update(MessageReceipt).where(*unread).values(read_at=utc_now()))
    await session.commit()
    return sorted(changed)


async def _set_delivered(session: AsyncSession, *conditions: ColumnElement[bool], commit: bool = True) -> list[int]:
    pending = (*conditions, MessageReceipt.delivered_at.is_(None))
    ids = list((await session.execute(select(MessageReceipt.message_id).where(*pending))).scalars())
    if ids:
        await session.execute(update(MessageReceipt).where(*pending).values(delivered_at=utc_now()))
    if commit:
        await session.commit()
    return sorted(set(ids))
