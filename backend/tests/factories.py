"""Minimal row builders for model/constraint tests."""

from itertools import count

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Conversation, ConversationMember, Message, User
from app.models.enums import ConversationType, MessageKind

_phone_numbers = count(1)


async def make_user(session: AsyncSession, name: str = "Test User") -> User:
    user = User(phone_number=f"+1555990{next(_phone_numbers):04d}", display_name=name, avatar_color="A100")
    session.add(user)
    await session.flush()
    return user


async def make_dm(session: AsyncSession, a: User, b: User) -> Conversation:
    conversation = Conversation(
        type=ConversationType.DIRECT,
        direct_key=f"{min(a.id, b.id)}:{max(a.id, b.id)}",
        avatar_color="A100",
        created_by=a.id,
    )
    session.add(conversation)
    await session.flush()
    session.add_all(
        [
            ConversationMember(conversation_id=conversation.id, user_id=a.id),
            ConversationMember(conversation_id=conversation.id, user_id=b.id),
        ]
    )
    await session.flush()
    return conversation


async def make_message(
    session: AsyncSession,
    conversation: Conversation,
    sender: User | None,
    body: str = "hello",
    client_id: str | None = None,
    reply_to_id: int | None = None,
) -> Message:
    message = Message(
        conversation_id=conversation.id,
        sender_id=sender.id if sender else None,
        kind=MessageKind.TEXT,
        body=body,
        client_id=client_id,
        reply_to_id=reply_to_id,
    )
    session.add(message)
    await session.flush()
    return message
