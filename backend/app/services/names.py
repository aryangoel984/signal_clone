"""How users are named for a given viewer: their nickname for that person (if saved as a
contact with one), else the profile display name, else the phone number."""

from collections.abc import Iterable

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Contact, Message, User
from app.models.enums import MessageKind


async def display_names(session: AsyncSession, viewer_id: int, user_ids: Iterable[int]) -> dict[int, str]:
    ids = set(user_ids)
    if not ids:
        return {}
    rows = await session.execute(
        select(User.id, User.display_name, User.phone_number, Contact.nickname)
        .outerjoin(Contact, and_(Contact.owner_id == viewer_id, Contact.contact_user_id == User.id))
        .where(User.id.in_(ids))
    )
    return {user_id: nickname or display_name or phone for user_id, display_name, phone, nickname in rows}


def user_ids_in(message: Message) -> set[int]:
    """Every user a message mentions: its sender plus a system message's actor/targets."""
    ids = {message.sender_id} if message.sender_id is not None else set()
    if message.kind is MessageKind.SYSTEM and message.system_data:
        ids.add(int(message.system_data.get("actor_id", 0)))
        ids.update(int(target) for target in message.system_data.get("target_ids", []))
    ids.discard(0)
    return ids


def describe_system_message(message: Message, viewer_id: int, names: dict[int, str]) -> str:
    """Viewer-relative text for a system message, e.g. "You created the group."."""
    data = message.system_data or {}
    actor_id = int(data.get("actor_id", 0))
    actor = "You" if actor_id == viewer_id else names.get(actor_id, "Someone")
    targets = _join([("you" if t == viewer_id else names.get(t, "someone")) for t in data.get("target_ids", [])])

    match data.get("event", message.body):
        case "group_created":
            return f"{actor} created the group."
        case "member_added":
            return f"{actor} added {targets}."
        case "member_removed":
            return f"{actor} removed {targets}."
        case "member_left":
            return f"{actor} left the group."
        case "group_renamed":
            return f'{actor} changed the group name to "{data.get("name", "")}".'
        case "group_avatar_changed":
            return f"{actor} changed the group photo."
        case "admin_granted":
            return f"{actor} made {targets} an admin."
        case "admin_revoked":
            return f"{actor} removed {targets} as an admin."
        case _:
            return message.body


def _join(items: list[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    return f"{', '.join(items[:-1])} and {items[-1]}"
