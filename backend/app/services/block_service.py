"""Blocking (PLAN 7.2). Anyone can be blocked, contact or not."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Block, Contact, User
from app.schemas.contact import UserPublic
from app.services.contact_service import to_public


class SelfBlockError(Exception):
    pass


class UserNotFoundError(Exception):
    pass


async def list_blocked(session: AsyncSession, viewer: User) -> list[UserPublic]:
    rows = await session.execute(
        select(User, Contact)
        .join(Block, (Block.blocked_id == User.id) & (Block.blocker_id == viewer.id))
        .outerjoin(Contact, (Contact.owner_id == viewer.id) & (Contact.contact_user_id == User.id))
        .order_by(Block.created_at)
    )
    return [to_public(user, contact) for user, contact in rows]


async def block(session: AsyncSession, viewer: User, user_id: int) -> None:
    """Idempotent."""
    if user_id == viewer.id:
        raise SelfBlockError
    if await session.get(User, user_id) is None:
        raise UserNotFoundError
    if await session.get(Block, (viewer.id, user_id)) is None:
        session.add(Block(blocker_id=viewer.id, blocked_id=user_id))
        await session.commit()


async def unblock(session: AsyncSession, viewer: User, user_id: int) -> None:
    """Idempotent. Messages sent during the block stay hidden: they were never delivered."""
    existing = await session.get(Block, (viewer.id, user_id))
    if existing is not None:
        await session.delete(existing)
        await session.commit()


async def has_blocked(session: AsyncSession, blocker_id: int, blocked_id: int) -> bool:
    return await session.get(Block, (blocker_id, blocked_id)) is not None
