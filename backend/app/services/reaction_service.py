"""Emoji reactions (PLAN 1.9): one per user per message; reacting again replaces it."""

from typing import Any, cast

from sqlalchemy import CursorResult, delete
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.models import Reaction, User
from app.models.enums import ConversationType
from app.services.message_service import (
    MessageNotFoundError,
    NotActiveMemberError,
    RecipientBlockedError,
    i_blocked_the_other,
    load_visible_message,
)
from app.ws.realtime import Realtime


async def set_reaction(session: AsyncSession, realtime: Realtime, viewer: User, message_id: int, emoji: str | None) -> None:
    """Sets my reaction (emoji) or removes it (None). Same rules as sending: only active
    members, and not in a DM with someone I blocked. Raises MessageNotFoundError,
    NotActiveMemberError or RecipientBlockedError."""
    message, member, conversation = await load_visible_message(session, viewer, message_id)
    if message.deleted_at is not None:
        raise MessageNotFoundError  # nothing left to react to
    if member.left_at is not None:
        raise NotActiveMemberError
    if conversation.type is ConversationType.DIRECT and await i_blocked_the_other(session, conversation.id, viewer.id):
        raise RecipientBlockedError

    if emoji is None:
        result = cast(
            CursorResult[Any],
            await session.execute(delete(Reaction).where(Reaction.message_id == message_id, Reaction.user_id == viewer.id)),
        )
        changed = result.rowcount > 0
    else:
        # Upsert: two tabs reacting at once can't hit the primary key twice.
        now = utc_now()
        await session.execute(
            insert(Reaction)
            .values(message_id=message_id, user_id=viewer.id, emoji=emoji, created_at=now, updated_at=now)
            .on_conflict_do_update(index_elements=["message_id", "user_id"], set_={"emoji": emoji, "updated_at": now})
        )
        changed = True
    await session.commit()
    if changed:
        await realtime.reaction_updated(message.conversation_id, message_id, viewer.id, emoji)
