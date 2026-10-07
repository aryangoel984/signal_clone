"""Message history and sending (PLAN 1.7, 1.8, section 2 "Messages")."""

from collections import defaultdict
from collections.abc import Sequence

from sqlalchemy import exists, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.models import Block, ConversationMember, Message, MessageReceipt, User, UserSettings
from app.models.enums import MessageKind, MessageStatus
from app.schemas.message import MessageOut, MessagePage
from app.services.conversation_service import load_membership
from app.services.message_queries import aggregate_status, visible_to
from app.services.names import describe_system_message, display_names, user_ids_in


class NotActiveMemberError(Exception):
    pass


class ClientIdConflictError(Exception):
    """The client_id was already used by this sender in a different conversation."""


async def list_messages(
    session: AsyncSession,
    viewer: User,
    conversation_id: int,
    *,
    before: int | None,
    after: int | None,
    limit: int,
) -> MessagePage:
    member, _ = await load_membership(session, viewer.id, conversation_id)
    query = select(Message).where(visible_to(member))

    if after is not None:  # catch-up after a reconnect: newer messages, oldest first
        rows = (await session.execute(query.where(Message.id > after).order_by(Message.id).limit(limit))).scalars().all()
        return MessagePage(items=await serialize(session, viewer, rows), next_cursor=None)

    if before is not None:
        query = query.where(Message.id < before)
    rows = (await session.execute(query.order_by(Message.id.desc()).limit(limit + 1))).scalars().all()
    has_older = len(rows) > limit
    page = list(reversed(rows[:limit]))
    return MessagePage(
        items=await serialize(session, viewer, page),
        next_cursor=page[0].id if has_older and page else None,
    )


async def send_message(
    session: AsyncSession, viewer: User, conversation_id: int, client_id: str, body: str
) -> tuple[MessageOut, bool]:
    """Returns (message, created). Retrying with the same client_id returns the original
    message instead of a duplicate (UNIQUE(sender_id, client_id))."""
    member, conversation = await load_membership(session, viewer.id, conversation_id)
    if member.left_at is not None:
        raise NotActiveMemberError

    existing = await _find_by_client_id(session, viewer.id, client_id)
    if existing is not None:
        return await _existing_result(session, viewer, existing, conversation_id)

    message = Message(
        conversation_id=conversation_id,
        sender_id=viewer.id,
        kind=MessageKind.TEXT,
        body=body,
        client_id=client_id,
        created_at=utc_now(),
    )
    session.add(message)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()  # a concurrent retry with the same client_id won the race
        winner = await _find_by_client_id(session, viewer.id, client_id)
        assert winner is not None
        return await _existing_result(session, viewer, winner, conversation_id)

    session.add_all(
        MessageReceipt(message_id=message.id, user_id=recipient_id, created_at=message.created_at)
        for recipient_id in await _recipient_ids(session, conversation_id, viewer.id)
    )
    conversation.last_message_at = message.created_at
    member.last_read_message_id = max(member.last_read_message_id, message.id)  # sending implies reading
    await session.commit()
    return (await serialize(session, viewer, [message]))[0], True


async def serialize(session: AsyncSession, viewer: User, messages: Sequence[Message]) -> list[MessageOut]:
    """Viewer-relative view of messages. Fixed number of queries regardless of page size."""
    if not messages:
        return []
    mentioned = set().union(*(user_ids_in(message) for message in messages))
    names = await display_names(session, viewer.id, mentioned)
    senders = {
        user.id: user
        for user in (
            await session.execute(select(User).where(User.id.in_({m.sender_id for m in messages if m.sender_id})))
        ).scalars()
    }
    statuses = await _statuses(session, viewer, [m.id for m in messages if m.sender_id == viewer.id and m.kind is MessageKind.TEXT])

    result: list[MessageOut] = []
    for message in messages:
        is_system = message.kind is MessageKind.SYSTEM
        is_mine = message.sender_id == viewer.id
        sender = senders.get(message.sender_id) if message.sender_id is not None else None
        if message.deleted_at is not None:
            text = "This message was deleted."
        elif is_system:
            text = describe_system_message(message, viewer.id, names)
        else:
            text = message.body
        result.append(
            MessageOut(
                id=message.id,
                conversation_id=message.conversation_id,
                client_id=message.client_id if is_mine else None,  # only meaningful to the sender
                kind=message.kind,
                text=text,
                sender_id=message.sender_id,
                sender_name=None if is_mine or is_system or message.sender_id is None else names.get(message.sender_id),
                sender_avatar_color=sender.avatar_color if sender else None,
                sender_avatar_url=sender.avatar_url if sender else None,
                created_at=message.created_at,
                status=statuses.get(message.id),
            )
        )
    return result


# --- helpers ---------------------------------------------------------------------------------


async def _find_by_client_id(session: AsyncSession, sender_id: int, client_id: str) -> Message | None:
    return await session.scalar(select(Message).where(Message.sender_id == sender_id, Message.client_id == client_id))


async def _existing_result(
    session: AsyncSession, viewer: User, message: Message, conversation_id: int
) -> tuple[MessageOut, bool]:
    if message.conversation_id != conversation_id:
        raise ClientIdConflictError
    return (await serialize(session, viewer, [message]))[0], False


async def _recipient_ids(session: AsyncSession, conversation_id: int, sender_id: int) -> list[int]:
    """Active members except the sender, minus anyone who has blocked the sender (PLAN 7.2)."""
    blocked_sender = exists().where(Block.blocker_id == ConversationMember.user_id, Block.blocked_id == sender_id)
    rows = await session.execute(
        select(ConversationMember.user_id).where(
            ConversationMember.conversation_id == conversation_id,
            ConversationMember.user_id != sender_id,
            ConversationMember.left_at.is_(None),
            ~blocked_sender,
        )
    )
    return list(rows.scalars())


async def _statuses(session: AsyncSession, viewer: User, message_ids: list[int]) -> dict[int, MessageStatus]:
    if not message_ids:
        return {}
    receipts = (await session.execute(select(MessageReceipt).where(MessageReceipt.message_id.in_(message_ids)))).scalars()
    by_message: defaultdict[int, list[MessageReceipt]] = defaultdict(list)
    for receipt in receipts:
        by_message[receipt.message_id].append(receipt)
    settings = await session.get(UserSettings, viewer.id)
    receipts_on = settings is None or settings.read_receipts_enabled

    statuses: dict[int, MessageStatus] = {}
    for message_id in message_ids:
        status = aggregate_status(by_message[message_id])
        if status is MessageStatus.READ and not receipts_on:
            status = MessageStatus.DELIVERED  # PLAN 7.4: you don't see reads when yours are off
        statuses[message_id] = status
    return statuses
