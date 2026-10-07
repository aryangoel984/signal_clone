import re

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Contact, User
from app.schemas.common import E164_PATTERN
from app.schemas.contact import AddContactRequest, UserPublic

SEARCH_LIMIT = 20
_SEPARATORS = re.compile(r"[\s\-().]")
_USERNAME_PREFIX = re.compile(r"^[a-z0-9_.]{1,32}$")


class UserNotFoundError(Exception):
    pass


class ContactExistsError(Exception):
    pass


class SelfContactError(Exception):
    pass


class ContactNotFoundError(Exception):
    pass


def to_public(user: User, contact: Contact | None) -> UserPublic:
    """Phone numbers are only shown for people the viewer has saved as contacts."""
    nickname = contact.nickname if contact else None
    return UserPublic(
        id=user.id,
        name=nickname or user.display_name or user.phone_number,
        display_name=user.display_name,
        username=user.username,
        about=user.about,
        avatar_url=user.avatar_url,
        avatar_color=user.avatar_color,
        phone_number=user.phone_number if contact else None,
        is_contact=contact is not None,
        nickname=nickname,
    )


async def list_contacts(session: AsyncSession, viewer: User) -> list[UserPublic]:
    rows = await session.execute(
        select(User, Contact).join(Contact, Contact.contact_user_id == User.id).where(Contact.owner_id == viewer.id)
    )
    contacts = [to_public(user, contact) for user, contact in rows]
    return sorted(contacts, key=lambda c: c.name.casefold())


async def add_contact(session: AsyncSession, viewer: User, request: AddContactRequest) -> UserPublic:
    if request.user_id is not None:
        user = await session.get(User, request.user_id)
    elif request.phone_number is not None:
        user = await session.scalar(select(User).where(User.phone_number == request.phone_number))
    else:
        user = await session.scalar(select(User).where(User.username == request.username))
    if user is None:
        raise UserNotFoundError
    if user.id == viewer.id:
        raise SelfContactError
    if await session.get(Contact, (viewer.id, user.id)) is not None:
        raise ContactExistsError

    contact = Contact(owner_id=viewer.id, contact_user_id=user.id, nickname=request.nickname)
    session.add(contact)
    await session.commit()
    return to_public(user, contact)


async def update_nickname(session: AsyncSession, viewer: User, user_id: int, nickname: str | None) -> UserPublic:
    contact = await session.get(Contact, (viewer.id, user_id))
    user = await session.get(User, user_id)
    if contact is None or user is None:
        raise ContactNotFoundError
    contact.nickname = nickname
    await session.commit()
    return to_public(user, contact)


async def remove_contact(session: AsyncSession, viewer: User, user_id: int) -> None:
    contact = await session.get(Contact, (viewer.id, user_id))
    if contact is None:
        raise ContactNotFoundError
    await session.delete(contact)
    await session.commit()


async def get_public_profile(session: AsyncSession, viewer: User, user_id: int) -> UserPublic:
    user = await session.get(User, user_id)
    if user is None:
        raise UserNotFoundError
    return to_public(user, await session.get(Contact, (viewer.id, user_id)))


async def search_users(session: AsyncSession, viewer: User, query: str) -> list[UserPublic]:
    """Finds people by exact phone number, username prefix, or - among the viewer's own
    contacts only - by name. Strangers can't be found by name."""
    query = query.strip()
    if not query:
        return []

    conditions = []
    phone = _SEPARATORS.sub("", query)
    if E164_PATTERN.fullmatch(phone):
        conditions.append(User.phone_number == phone)
    username = query.removeprefix("@").lower()
    if _USERNAME_PREFIX.fullmatch(username):
        conditions.append(User.username.startswith(username, autoescape=True))

    by_name = (
        select(Contact.contact_user_id)
        .join(User, User.id == Contact.contact_user_id)
        .where(
            Contact.owner_id == viewer.id,
            or_(User.display_name.icontains(query, autoescape=True), Contact.nickname.icontains(query, autoescape=True)),
        )
    )
    conditions.append(User.id.in_(by_name))

    rows = await session.execute(
        select(User, Contact)
        .outerjoin(Contact, (Contact.owner_id == viewer.id) & (Contact.contact_user_id == User.id))
        .where(or_(*conditions), User.id != viewer.id, User.display_name.is_not(None))
        .limit(SEARCH_LIMIT)
    )
    results = [to_public(user, contact) for user, contact in rows]
    # Contacts first, then alphabetical.
    return sorted(results, key=lambda r: (not r.is_contact, r.name.casefold()))
