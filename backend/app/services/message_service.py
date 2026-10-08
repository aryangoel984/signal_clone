"""Message history and sending (PLAN 1.7, 1.8, section 2 "Messages")."""

from collections.abc import Sequence

from sqlalchemy import exists, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.models import Block, Conversation, ConversationMember, Message, MessageReceipt, Reaction, User, UserSettings
from app.models.enums import ConversationType, MessageKind
from app.schemas.message import MessageDetails, MessageOut, MessagePage, Quote, ReactionOut, Recipient
from app.services.conversation_service import ConversationNotFoundError, load_membership
from app.services.message_queries import current_member_receipts, statuses_for, visible_to
from app.services.names import describe_system_message, display_names, user_ids_in
from app.ws.realtime import Realtime


class NotActiveMemberError(Exception):
    pass


class ClientIdConflictError(Exception):
    """The client_id was already used by this sender in a different conversation."""


class RecipientBlockedError(Exception):
    """I blocked the other person in this DM: unblock to send (PLAN 7.2)."""


class MessageNotFoundError(Exception):
    pass


class InvalidReplyError(Exception):
    """reply_to_id isn't a text message the sender can see in this conversation."""


class NotSenderError(Exception):
    pass


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
    session: AsyncSession,
    realtime: Realtime,
    viewer: User,
    conversation_id: int,
    client_id: str,
    body: str,
    reply_to_id: int | None = None,
) -> tuple[MessageOut, bool]:
    """Returns (message, created). Retrying with the same client_id returns the original
    message instead of a duplicate (UNIQUE(sender_id, client_id)) and broadcasts nothing."""
    member, conversation = await load_membership(session, viewer.id, conversation_id)
    if member.left_at is not None:
        raise NotActiveMemberError
    if conversation.type is ConversationType.DIRECT and await i_blocked_the_other(session, conversation_id, viewer.id):
        raise RecipientBlockedError
    # The reverse (they blocked me) is deliberately not an error: my send "succeeds", but they
    # get no receipt row and no push, so it stays at one tick (Signal doesn't reveal blocks).

    existing = await _find_by_client_id(session, viewer.id, client_id)
    if existing is not None:
        return await _existing_result(session, viewer, existing, conversation_id)
    if reply_to_id is not None and not await _can_quote(session, member, reply_to_id):
        raise InvalidReplyError

    message = Message(
        conversation_id=conversation_id,
        sender_id=viewer.id,
        kind=MessageKind.TEXT,
        body=body,
        client_id=client_id,
        reply_to_id=reply_to_id,
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
    result = (await serialize(session, viewer, [message]))[0]
    await realtime.message_created(message.id)  # after the commit: message.new + delivered
    return result, True


async def serialize(session: AsyncSession, viewer: User, messages: Sequence[Message]) -> list[MessageOut]:
    """Viewer-relative view of messages. Fixed number of queries regardless of page size."""
    if not messages:
        return []
    originals = await _visible_originals(session, viewer.id, messages)
    mentioned = set().union(*(user_ids_in(message) for message in [*messages, *originals.values()]))
    names = await display_names(session, viewer.id, mentioned)
    reactions = await _reactions_for(session, viewer.id, [m.id for m in messages])
    senders = {
        user.id: user
        for user in (
            await session.execute(select(User).where(User.id.in_({m.sender_id for m in messages if m.sender_id})))
        ).scalars()
    }
    statuses = await statuses_for(session, viewer, [m.id for m in messages if m.sender_id == viewer.id and m.kind is MessageKind.TEXT])

    result: list[MessageOut] = []
    for message in messages:
        is_system = message.kind is MessageKind.SYSTEM
        is_mine = message.sender_id == viewer.id
        sender = senders.get(message.sender_id) if message.sender_id is not None else None
        text = describe_system_message(message, viewer.id, names) if is_system else _text_of(message)
        original = originals.get(message.reply_to_id) if message.reply_to_id is not None else None
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
                reply_to_id=message.reply_to_id,
                quote=_quote(original, viewer.id, names) if original else None,
                reactions=reactions.get(message.id, []),
            )
        )
    return result


async def load_visible_message(session: AsyncSession, viewer: User, message_id: int) -> tuple[Message, ConversationMember, Conversation]:
    """A text message the viewer can see, with their membership. MessageNotFoundError
    otherwise, also for conversations they were never in (we don't reveal they exist)."""
    message = await session.get(Message, message_id)
    if message is None or message.kind is not MessageKind.TEXT:
        raise MessageNotFoundError
    try:
        member, conversation = await load_membership(session, viewer.id, message.conversation_id)
    except ConversationNotFoundError:
        raise MessageNotFoundError from None
    if not await session.scalar(select(Message.id).where(Message.id == message_id, visible_to(member))):
        raise MessageNotFoundError
    return message, member, conversation


# --- helpers ---------------------------------------------------------------------------------


def _text_of(message: Message) -> str:
    return "This message was deleted." if message.deleted_at is not None else message.body


def _quote(original: Message, viewer_id: int, names: dict[int, str]) -> Quote:
    sender_id = original.sender_id
    if sender_id is None:
        author = "Deleted user"
    elif sender_id == viewer_id:
        author = "You"
    else:
        author = names.get(sender_id, "Deleted user")
    return Quote(id=original.id, sender_id=sender_id, author_name=author, text=_text_of(original))


async def _can_quote(session: AsyncSession, member: ConversationMember, message_id: int) -> bool:
    """Only a text message of this conversation that the sender can see."""
    found = await session.scalar(
        select(Message.id).where(Message.id == message_id, Message.kind == MessageKind.TEXT, visible_to(member))
    )
    return found is not None


async def _visible_originals(session: AsyncSession, viewer_id: int, messages: Sequence[Message]) -> dict[int, Message]:
    """The quoted originals of these replies, keeping only those the viewer may see (an original
    sent before they joined, or by someone they blocked after blocking, stays hidden)."""
    reply_ids = {m.reply_to_id for m in messages if m.reply_to_id is not None}
    if not reply_ids:
        return {}
    members = (
        await session.execute(
            select(ConversationMember).where(
                ConversationMember.user_id == viewer_id,
                ConversationMember.conversation_id.in_({m.conversation_id for m in messages}),
            )
        )
    ).scalars().all()
    if not members:
        return {}
    rows = await session.execute(
        select(Message).where(Message.id.in_(reply_ids), Message.kind == MessageKind.TEXT, or_(*(visible_to(m) for m in members)))
    )
    return {message.id: message for message in rows.scalars()}


async def _reactions_for(session: AsyncSession, viewer_id: int, message_ids: list[int]) -> dict[int, list[ReactionOut]]:
    """Reactions per message, oldest first, minus reactions from people the viewer blocked."""
    blocked = select(Block.blocked_id).where(Block.blocker_id == viewer_id)
    rows = await session.execute(
        select(Reaction)
        .where(Reaction.message_id.in_(message_ids), Reaction.user_id.not_in(blocked))
        .order_by(Reaction.created_at, Reaction.user_id)
    )
    by_message: dict[int, list[ReactionOut]] = {}
    for reaction in rows.scalars():
        by_message.setdefault(reaction.message_id, []).append(ReactionOut(user_id=reaction.user_id, emoji=reaction.emoji))
    return by_message


async def _find_by_client_id(session: AsyncSession, sender_id: int, client_id: str) -> Message | None:
    return await session.scalar(select(Message).where(Message.sender_id == sender_id, Message.client_id == client_id))


async def _existing_result(
    session: AsyncSession, viewer: User, message: Message, conversation_id: int
) -> tuple[MessageOut, bool]:
    if message.conversation_id != conversation_id:
        raise ClientIdConflictError
    return (await serialize(session, viewer, [message]))[0], False


async def i_blocked_the_other(session: AsyncSession, conversation_id: int, viewer_id: int) -> bool:
    other = select(ConversationMember.user_id).where(
        ConversationMember.conversation_id == conversation_id, ConversationMember.user_id != viewer_id
    )
    found = await session.scalar(select(Block.blocked_id).where(Block.blocker_id == viewer_id, Block.blocked_id.in_(other)))
    return found is not None


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


async def get_details(session: AsyncSession, viewer: User, message_id: int) -> MessageDetails:
    """"Message details" for the sender: each current member's delivered/read time.
    404 if the viewer can't see the message, 403 if they can but didn't send it."""
    message, _, _ = await load_visible_message(session, viewer, message_id)
    if message.sender_id != viewer.id:
        raise NotSenderError

    receipts = (await session.execute(current_member_receipts([message_id]))).scalars().all()
    users = {u.id: u for u in (await session.execute(select(User).where(User.id.in_([r.user_id for r in receipts])))).scalars()}
    names = await display_names(session, viewer.id, users)
    settings = await session.get(UserSettings, viewer.id)
    show_reads = settings is None or settings.read_receipts_enabled
    recipients = [
        Recipient(
            user_id=r.user_id,
            name=names[r.user_id],
            avatar_color=users[r.user_id].avatar_color,
            avatar_url=users[r.user_id].avatar_url,
            delivered_at=r.delivered_at,
            read_at=r.read_at if show_reads else None,
        )
        for r in receipts
    ]
    return MessageDetails(message_id=message_id, sent_at=message.created_at, recipients=sorted(recipients, key=lambda r: r.name.casefold()))
