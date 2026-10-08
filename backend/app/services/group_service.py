"""Group management (PLAN section 2 "Groups", 1.6 history rules, 7.1). Every change adds a
system message to the timeline and, after the commit, notifies members over WebSockets."""

from pathlib import Path
from typing import Any, cast

from fastapi import UploadFile
from sqlalchemy import CursorResult, exists, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.avatar_colors import avatar_color_for
from app.core.time import utc_now
from app.models import Conversation, ConversationMember, Message, User
from app.models.enums import ConversationType, MemberRole, MessageKind
from app.schemas.conversation import ConversationDetail
from app.services.conversation_service import ConversationNotFoundError, get_conversation, load_membership
from app.services.media import delete_media, save_image
from app.ws.realtime import Realtime

MAX_GROUP_MEMBERS = 50


class NotAdminError(Exception):
    pass


class GroupFullError(Exception):
    pass


class InvalidMembersError(Exception):
    pass


class AlreadyMembersError(Exception):
    pass


class LastAdminError(Exception):
    pass


class MemberNotFoundError(Exception):
    pass


# --- create / rename / photo --------------------------------------------------------------------


async def create_group(
    session: AsyncSession, realtime: Realtime, creator: User, name: str, member_ids: list[int]
) -> ConversationDetail:
    others = sorted(set(member_ids) - {creator.id})
    if not others:
        raise InvalidMembersError("Add at least one other member")
    if len(others) + 1 > MAX_GROUP_MEMBERS:
        raise GroupFullError
    await _require_real_users(session, others)

    conversation = Conversation(
        type=ConversationType.GROUP, name=name, avatar_color=avatar_color_for(f"group:{name}"), created_by=creator.id
    )
    session.add(conversation)
    await session.flush()
    session.add(ConversationMember(conversation_id=conversation.id, user_id=creator.id, role=MemberRole.ADMIN))
    session.add_all(ConversationMember(conversation_id=conversation.id, user_id=user_id) for user_id in others)
    message = await _system_message(session, conversation, creator.id, "group_created")
    creator_member = await session.get(ConversationMember, (conversation.id, creator.id))
    assert creator_member is not None
    creator_member.last_read_message_id = message.id
    await session.commit()

    await realtime.message_created(message.id)
    await realtime.group_updated(conversation.id, "created", creator.id, others)
    return await get_conversation(session, realtime, creator, conversation.id)


async def rename_group(
    session: AsyncSession, realtime: Realtime, viewer: User, conversation_id: int, name: str
) -> ConversationDetail:
    member, conversation = await _admin_of_group(session, viewer, conversation_id)
    if name != conversation.name:
        conversation.name = name
        message = await _system_message(session, conversation, viewer.id, "group_renamed", extra={"name": name})
        await session.commit()
        await realtime.message_created(message.id)
        await realtime.group_updated(conversation_id, "renamed", viewer.id, [])
    return await get_conversation(session, realtime, viewer, conversation_id)


async def set_group_avatar(
    session: AsyncSession,
    realtime: Realtime,
    viewer: User,
    conversation_id: int,
    upload: UploadFile | None,
    uploads_dir: Path,
) -> ConversationDetail:
    """upload=None removes the photo. Raises media.* errors for bad images."""
    _, conversation = await _admin_of_group(session, viewer, conversation_id)
    new_url = await save_image(upload, uploads_dir, "groups", str(conversation_id)) if upload else None
    old_url = conversation.avatar_url
    conversation.avatar_url = new_url
    message = await _system_message(session, conversation, viewer.id, "group_avatar_changed")
    await session.commit()
    await delete_media(old_url, uploads_dir)
    await realtime.message_created(message.id)
    await realtime.group_updated(conversation_id, "avatar_changed", viewer.id, [])
    return await get_conversation(session, realtime, viewer, conversation_id)


# --- members -------------------------------------------------------------------------------------


async def add_members(
    session: AsyncSession, realtime: Realtime, viewer: User, conversation_id: int, user_ids: list[int]
) -> ConversationDetail:
    """Adds new people or re-adds former members. Either way they only see messages from
    now on (PLAN 1.6 re-add rule): history_start_id = the latest message before this one."""
    _, conversation = await _admin_of_group(session, viewer, conversation_id)
    active = set(await _active_member_ids(session, conversation_id))
    new_ids = sorted(set(user_ids) - active)
    if not new_ids:
        raise AlreadyMembersError
    if len(active) + len(new_ids) > MAX_GROUP_MEMBERS:
        raise GroupFullError
    await _require_real_users(session, new_ids)

    latest = await session.scalar(select(func.max(Message.id)).where(Message.conversation_id == conversation_id)) or 0
    now = utc_now()
    for user_id in new_ids:
        row = await session.get(ConversationMember, (conversation_id, user_id))
        if row is None:
            row = ConversationMember(conversation_id=conversation_id, user_id=user_id)
            session.add(row)
        row.role = MemberRole.MEMBER
        row.left_at = None
        row.history_end_id = None
        row.history_start_id = latest
        row.last_read_message_id = latest
        row.joined_at = now
    message = await _system_message(session, conversation, viewer.id, "member_added", targets=new_ids)
    await session.commit()

    await realtime.message_created(message.id)
    await realtime.group_updated(conversation_id, "members_added", viewer.id, new_ids)
    return await get_conversation(session, realtime, viewer, conversation_id)


async def remove_member(
    session: AsyncSession, realtime: Realtime, viewer: User, conversation_id: int, target_id: int
) -> None:
    """An admin removes someone, or anyone removes themselves (leaving). The last admin
    can't leave while others remain. The check and the write are one conditional UPDATE, so
    two admins leaving at once can't both succeed."""
    member, conversation = await _group_membership(session, viewer, conversation_id)
    leaving = target_id == viewer.id
    if member.left_at is not None:
        raise MemberNotFoundError
    if not leaving and member.role is not MemberRole.ADMIN:
        raise NotAdminError
    target = await session.get(ConversationMember, (conversation_id, target_id))
    if target is None or target.left_at is not None:
        raise MemberNotFoundError

    message = await _system_message(
        session,
        conversation,
        viewer.id,
        "member_left" if leaving else "member_removed",
        targets=[] if leaving else [target_id],
    )
    others, other_admin = aliased(ConversationMember), aliased(ConversationMember)
    keeps_an_admin = or_(
        ConversationMember.role != MemberRole.ADMIN,
        exists().where(
            other_admin.conversation_id == conversation_id,
            other_admin.user_id != target_id,
            other_admin.role == MemberRole.ADMIN,
            other_admin.left_at.is_(None),
        ),
        ~exists().where(  # the last person in the group may always leave
            others.conversation_id == conversation_id, others.user_id != target_id, others.left_at.is_(None)
        ),
    )
    result = cast(
        CursorResult[Any],
        await session.execute(
            update(ConversationMember)
            .where(
                ConversationMember.conversation_id == conversation_id,
                ConversationMember.user_id == target_id,
                ConversationMember.left_at.is_(None),
                keeps_an_admin,
            )
            .values(left_at=utc_now(), history_end_id=message.id)  # they see their own removal, nothing after
            .execution_options(synchronize_session=False)
        ),
    )
    if result.rowcount == 0:
        await session.rollback()  # also discards the system message
        raise LastAdminError
    await session.commit()

    await realtime.message_created(message.id, extra_recipient_ids=(target_id,))
    await realtime.group_updated(
        conversation_id,
        "member_left" if leaving else "member_removed",
        viewer.id,
        [target_id],
        extra_recipient_ids=(target_id,),
    )


async def change_role(
    session: AsyncSession, realtime: Realtime, viewer: User, conversation_id: int, target_id: int, role: MemberRole
) -> ConversationDetail:
    """Promote or demote. Demoting the last admin is refused, atomically like removal."""
    _, conversation = await _admin_of_group(session, viewer, conversation_id)
    target = await session.get(ConversationMember, (conversation_id, target_id))
    if target is None or target.left_at is not None:
        raise MemberNotFoundError
    if target.role is role:
        return await get_conversation(session, realtime, viewer, conversation_id)

    promote = role is MemberRole.ADMIN
    message = await _system_message(
        session, conversation, viewer.id, "admin_granted" if promote else "admin_revoked", targets=[target_id]
    )
    other_admin = aliased(ConversationMember)
    another_admin_remains = exists().where(
        other_admin.conversation_id == conversation_id,
        other_admin.user_id != target_id,
        other_admin.role == MemberRole.ADMIN,
        other_admin.left_at.is_(None),
    )
    conditions = [
        ConversationMember.conversation_id == conversation_id,
        ConversationMember.user_id == target_id,
        ConversationMember.left_at.is_(None),
    ]
    if not promote:
        conditions.append(another_admin_remains)
    result = cast(
        CursorResult[Any],
        await session.execute(
            update(ConversationMember).where(*conditions).values(role=role).execution_options(synchronize_session=False)
        ),
    )
    if result.rowcount == 0:
        await session.rollback()
        raise LastAdminError
    await session.commit()
    # The UPDATE bypassed the ORM: drop the cached row so the response reloads the new role.
    session.expire(target)

    await realtime.message_created(message.id)
    await realtime.group_updated(conversation_id, "role_changed", viewer.id, [target_id])
    return await get_conversation(session, realtime, viewer, conversation_id)


# --- helpers ------------------------------------------------------------------------------------------


async def _group_membership(
    session: AsyncSession, viewer: User, conversation_id: int
) -> tuple[ConversationMember, Conversation]:
    member, conversation = await load_membership(session, viewer.id, conversation_id)
    if conversation.type is not ConversationType.GROUP:
        raise ConversationNotFoundError  # group endpoints don't apply to DMs
    return member, conversation


async def _admin_of_group(
    session: AsyncSession, viewer: User, conversation_id: int
) -> tuple[ConversationMember, Conversation]:
    member, conversation = await _group_membership(session, viewer, conversation_id)
    if member.left_at is not None or member.role is not MemberRole.ADMIN:
        raise NotAdminError
    return member, conversation


async def _active_member_ids(session: AsyncSession, conversation_id: int) -> list[int]:
    rows = await session.execute(
        select(ConversationMember.user_id).where(
            ConversationMember.conversation_id == conversation_id, ConversationMember.left_at.is_(None)
        )
    )
    return list(rows.scalars())


async def _require_real_users(session: AsyncSession, user_ids: list[int]) -> None:
    """Every id must be an existing user who finished onboarding."""
    found = await session.execute(select(User.id).where(User.id.in_(user_ids), User.display_name.is_not(None)))
    if len(set(found.scalars())) != len(set(user_ids)):
        raise InvalidMembersError("Some members don't exist")


async def _system_message(
    session: AsyncSession,
    conversation: Conversation,
    actor_id: int,
    event: str,
    targets: list[int] | None = None,
    extra: dict[str, Any] | None = None,
) -> Message:
    message = Message(
        conversation_id=conversation.id,
        sender_id=actor_id,
        kind=MessageKind.SYSTEM,
        body=event,
        system_data={"event": event, "actor_id": actor_id, "target_ids": targets or [], **(extra or {})},
        created_at=utc_now(),
    )
    session.add(message)
    await session.flush()
    conversation.last_message_at = message.created_at
    return message
