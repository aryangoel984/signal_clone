from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.avatar_colors import avatar_color_for
from app.models import Block, Contact, Conversation, ConversationMember, Message, MessageReceipt, User, UserSettings
from app.models.enums import ConversationType, MessageKind, MessageStatus
from app.schemas.conversation import (
    ConversationDetail,
    ConversationSummary,
    LastMessage,
    MemberOut,
    UpdatePreferencesRequest,
)
from app.services.message_queries import group_appearance, last_visible_message, statuses_for, unread_count
from app.services.names import describe_system_message, display_names, user_ids_in
from app.ws.realtime import Realtime


class ConversationNotFoundError(Exception):
    pass


class UserNotFoundError(Exception):
    pass


class SelfConversationError(Exception):
    pass


@dataclass
class _Context:
    """Everything about the viewer that every row needs, loaded once per request."""

    viewer_id: int
    viewer: User
    read_receipts_on: bool
    contact_ids: set[int]
    blocked_ids: set[int]
    realtime: Realtime


async def list_conversations(
    session: AsyncSession, realtime: Realtime, viewer: User, *, archived: bool
) -> list[ConversationSummary]:
    """The chat list. Preview, unread count and ordering only consider messages the viewer
    can see (history range + blocks, PLAN 1.6). Empty DMs are hidden (PLAN 7.3).
    Roughly three small indexed queries per conversation: fine at demo scale.
    Loading the list also counts as the client receiving its pending messages (delivered),
    in case its WebSocket isn't connected."""
    await realtime.deliver_pending(viewer.id)
    rows = (
        await session.execute(
            select(ConversationMember, Conversation)
            .join(Conversation, Conversation.id == ConversationMember.conversation_id)
            .where(ConversationMember.user_id == viewer.id, ConversationMember.is_archived.is_(archived))
        )
    ).all()
    context = await _load_context(session, realtime, viewer)
    members_by_conversation = await _active_members(session, [conversation.id for _, conversation in rows])

    summaries: list[ConversationSummary] = []
    for member, conversation in rows:
        summary = await _summarize(session, context, member, conversation, members_by_conversation[conversation.id])
        if conversation.type is ConversationType.DIRECT and summary.last_message is None:
            continue
        summaries.append(summary)

    summaries.sort(key=lambda s: s.sort_at, reverse=True)
    summaries.sort(key=lambda s: not s.is_pinned)  # stable: pinned first, each group newest first
    return summaries


async def get_conversation(
    session: AsyncSession, realtime: Realtime, viewer: User, conversation_id: int
) -> ConversationDetail:
    member, conversation = await load_membership(session, viewer.id, conversation_id)
    context = await _load_context(session, realtime, viewer)
    members = (await _active_members(session, [conversation.id]))[conversation.id]
    summary = await _summarize(session, context, member, conversation, members)
    names = await display_names(session, viewer.id, [user.id for user, _ in members])
    return ConversationDetail(
        **summary.model_dump(),
        members=[
            MemberOut(
                user_id=user.id,
                name="You" if user.id == viewer.id else names[user.id],
                avatar_url=user.avatar_url,
                avatar_color=user.avatar_color,
                role=membership.role,
            )
            for user, membership in members
        ],
        my_role=member.role,
        groups_in_common=await _groups_in_common(session, viewer.id, summary.other_user_id)
        if summary.other_user_id is not None
        else [],
        last_read_message_id=member.last_read_message_id,
    )


async def get_or_create_direct(
    session: AsyncSession, realtime: Realtime, viewer: User, other_user_id: int
) -> tuple[ConversationDetail, bool]:
    """Returns (conversation, created). The UNIQUE direct_key makes concurrent calls safe."""
    if other_user_id == viewer.id:
        raise SelfConversationError
    other = await session.get(User, other_user_id)
    if other is None:
        raise UserNotFoundError

    direct_key = f"{min(viewer.id, other.id)}:{max(viewer.id, other.id)}"
    existing = await session.scalar(select(Conversation.id).where(Conversation.direct_key == direct_key))
    if existing is not None:
        return await get_conversation(session, realtime, viewer, existing), False

    conversation = Conversation(
        type=ConversationType.DIRECT,
        direct_key=direct_key,
        avatar_color=avatar_color_for(direct_key),
        created_by=viewer.id,
    )
    session.add(conversation)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()  # another request created it first
        existing_id = (await session.execute(select(Conversation.id).where(Conversation.direct_key == direct_key))).scalar_one()
        return await get_conversation(session, realtime, viewer, existing_id), False

    session.add_all(
        [
            ConversationMember(conversation_id=conversation.id, user_id=viewer.id),
            ConversationMember(conversation_id=conversation.id, user_id=other.id),
        ]
    )
    await session.commit()
    return await get_conversation(session, realtime, viewer, conversation.id), True


async def update_preferences(
    session: AsyncSession, realtime: Realtime, viewer: User, conversation_id: int, changes: UpdatePreferencesRequest
) -> ConversationDetail:
    member, _ = await load_membership(session, viewer.id, conversation_id)
    for name, value in changes.model_dump(exclude_unset=True).items():
        setattr(member, name, value)
    await session.commit()
    return await get_conversation(session, realtime, viewer, conversation_id)


# --- helpers ----------------------------------------------------------------------------


async def load_membership(session: AsyncSession, viewer_id: int, conversation_id: int) -> tuple[ConversationMember, Conversation]:
    """404 unless the viewer is or was a member: we don't reveal that other conversations exist."""
    row = (
        await session.execute(
            select(ConversationMember, Conversation)
            .join(Conversation, Conversation.id == ConversationMember.conversation_id)
            .where(ConversationMember.conversation_id == conversation_id, ConversationMember.user_id == viewer_id)
        )
    ).one_or_none()
    if row is None:
        raise ConversationNotFoundError
    member, conversation = row
    return member, conversation


async def _groups_in_common(session: AsyncSession, viewer_id: int, other_id: int) -> list[str]:
    mine, theirs = aliased(ConversationMember), aliased(ConversationMember)
    rows = await session.execute(
        select(Conversation.name)
        .join(mine, (mine.conversation_id == Conversation.id) & (mine.user_id == viewer_id))
        .join(theirs, (theirs.conversation_id == Conversation.id) & (theirs.user_id == other_id))
        .where(Conversation.type == ConversationType.GROUP, mine.left_at.is_(None), theirs.left_at.is_(None))
        .order_by(Conversation.name)
    )
    return [name for name in rows.scalars() if name is not None]


async def _load_context(session: AsyncSession, realtime: Realtime, viewer: User) -> _Context:
    settings = await session.get(UserSettings, viewer.id)
    contact_ids = set(
        (await session.execute(select(Contact.contact_user_id).where(Contact.owner_id == viewer.id))).scalars()
    )
    return _Context(
        viewer_id=viewer.id,
        viewer=viewer,
        read_receipts_on=settings.read_receipts_enabled if settings else True,
        contact_ids=contact_ids,
        blocked_ids=set((await session.execute(select(Block.blocked_id).where(Block.blocker_id == viewer.id))).scalars()),
        realtime=realtime,
    )


async def _active_members(
    session: AsyncSession, conversation_ids: list[int]
) -> defaultdict[int, list[tuple[User, ConversationMember]]]:
    by_conversation: defaultdict[int, list[tuple[User, ConversationMember]]] = defaultdict(list)
    if not conversation_ids:
        return by_conversation
    rows = await session.execute(
        select(User, ConversationMember)
        .join(ConversationMember, ConversationMember.user_id == User.id)
        .where(ConversationMember.conversation_id.in_(conversation_ids), ConversationMember.left_at.is_(None))
        .order_by(ConversationMember.joined_at)
    )
    for user, membership in rows:
        by_conversation[membership.conversation_id].append((user, membership))
    return by_conversation


async def _summarize(
    session: AsyncSession,
    context: _Context,
    member: ConversationMember,
    conversation: Conversation,
    members: list[tuple[User, ConversationMember]],
) -> ConversationSummary:
    last = await last_visible_message(session, member)
    other = next((user for user, _ in members if user.id != context.viewer_id), None)
    is_direct = conversation.type is ConversationType.DIRECT

    mentioned = user_ids_in(last) if last else set()
    if is_direct and other is not None:
        mentioned.add(other.id)
    names = await display_names(session, context.viewer_id, mentioned)

    if is_direct:
        title = names.get(other.id, "Unknown") if other else "Deleted user"
        avatar_url, avatar_color = (other.avatar_url, other.avatar_color) if other else (None, conversation.avatar_color)
    else:
        title, avatar_url = await group_appearance(session, context.viewer_id, conversation)
        avatar_color = conversation.avatar_color

    return ConversationSummary(
        id=conversation.id,
        type=conversation.type,
        title=title,
        avatar_url=avatar_url,
        avatar_color=avatar_color,
        other_user_id=other.id if is_direct and other else None,
        other_user_online=context.realtime.is_online(other.id) if is_direct and other else None,
        other_user_last_seen_at=other.last_seen_at if is_direct and other else None,
        is_contact=(other.id in context.contact_ids) if is_direct and other else None,
        blocked_by_me=(other.id in context.blocked_ids) if is_direct and other else None,
        member_count=len(members),
        is_pinned=member.is_pinned,
        is_archived=member.is_archived,
        muted_until=member.muted_until,
        can_send=member.left_at is None,
        unread_count=await unread_count(session, member),
        last_message=await _last_message(session, context, last, names) if last else None,
        sort_at=last.created_at if last else conversation.created_at,
    )


async def _last_message(
    session: AsyncSession, context: _Context, message: Message, names: dict[int, str]
) -> LastMessage:
    is_system = message.kind is MessageKind.SYSTEM
    is_mine = message.sender_id == context.viewer_id
    if message.deleted_at is not None:
        text = "This message was deleted."
    elif is_system:
        text = describe_system_message(message, context.viewer_id, names)
    else:
        text = message.body

    status = None
    if is_mine and not is_system:
        status = (await statuses_for(session, context.viewer, [message.id]))[message.id]

    return LastMessage(
        id=message.id,
        kind=message.kind,
        text=text,
        sender_id=message.sender_id,
        sender_name=None if is_system or is_mine or message.sender_id is None else names.get(message.sender_id),
        created_at=message.created_at,
        status=status,
    )
