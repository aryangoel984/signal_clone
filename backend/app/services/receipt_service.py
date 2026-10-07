"""Delivery and read state (PLAN 1.6, 1.8, 7.4)."""

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.models import ConversationMember, Message, MessageReceipt, User, UserSettings
from app.services.message_queries import visible_to


async def mark_all_delivered(session: AsyncSession, user_id: int) -> None:
    """Everything waiting for this user counts as delivered once their client fetches it.
    Until WebSockets (phase 5) this runs when the chat list is loaded; the partial index
    ix_receipts_user_undelivered keeps it cheap."""
    await session.execute(
        update(MessageReceipt)
        .where(MessageReceipt.user_id == user_id, MessageReceipt.delivered_at.is_(None))
        .values(delivered_at=utc_now())
    )
    await session.commit()


async def mark_read(session: AsyncSession, viewer: User, member: ConversationMember, up_to_message_id: int) -> None:
    """Moves the read watermark forward (never back), clamped to the newest message the
    member can see. read_at is only recorded if the reader has read receipts on."""
    newest_visible = await session.scalar(select(func.max(Message.id)).where(visible_to(member)))
    target = min(up_to_message_id, newest_visible or 0)
    if target <= member.last_read_message_id:
        return
    member.last_read_message_id = target

    in_range = MessageReceipt.message_id.in_(
        select(Message.id).where(Message.conversation_id == member.conversation_id, Message.id <= target)
    )
    mine = (MessageReceipt.user_id == viewer.id, in_range)
    now = utc_now()
    # A message on screen has been delivered, whatever the read-receipt setting
    # (and the CHECK read_implies_delivered needs delivered_at before read_at).
    await session.execute(update(MessageReceipt).where(*mine, MessageReceipt.delivered_at.is_(None)).values(delivered_at=now))

    settings = await session.get(UserSettings, viewer.id)
    if settings is None or settings.read_receipts_enabled:
        await session.execute(update(MessageReceipt).where(*mine, MessageReceipt.read_at.is_(None)).values(read_at=now))
    await session.commit()
