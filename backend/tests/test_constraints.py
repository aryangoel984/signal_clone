import pytest
from sqlalchemy import ColumnElement, delete, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.models import (
    Attachment,
    Block,
    Contact,
    Conversation,
    ConversationMember,
    Message,
    MessageReceipt,
    Reaction,
    User,
    UserSession,
    UserSettings,
)
from app.models.enums import ConversationType
from tests.factories import make_dm, make_message, make_user

NOW = "'2026-01-01 00:00:00.000000'"


async def count(session: AsyncSession, model: type, *conditions: ColumnElement[bool]) -> int:
    query = select(func.count()).select_from(model).where(*conditions)
    return (await session.execute(query)).scalar_one()


# --- enums -------------------------------------------------------------------------


async def test_lowercase_enum_values_pass_check_in_raw_sql(session: AsyncSession) -> None:
    await session.execute(
        text(
            "INSERT INTO conversations (type, direct_key, avatar_color, created_at, updated_at) "
            f"VALUES ('direct', '1:2', 'A100', {NOW}, {NOW})"
        )
    )
    await session.execute(
        text(
            "INSERT INTO conversations (type, name, avatar_color, created_at, updated_at) "
            f"VALUES ('group', 'Friends', 'A100', {NOW}, {NOW})"
        )
    )

    stored = (await session.execute(text("SELECT type FROM conversations ORDER BY id"))).scalars().all()
    assert stored == ["direct", "group"]


async def test_uppercase_enum_value_is_rejected(session: AsyncSession) -> None:
    with pytest.raises(IntegrityError, match="ck_conversations_type"):
        await session.execute(
            text(
                "INSERT INTO conversations (type, name, avatar_color, created_at, updated_at) "
                f"VALUES ('GROUP', 'Friends', 'A100', {NOW}, {NOW})"
            )
        )


async def test_orm_stores_enum_value_not_member_name(session: AsyncSession) -> None:
    a, b = await make_user(session), await make_user(session)
    await make_dm(session, a, b)

    assert (await session.execute(text("SELECT type FROM conversations"))).scalar_one() == "direct"


# --- DM uniqueness ---------------------------------------------------------------


async def test_second_dm_for_same_pair_is_rejected(session: AsyncSession) -> None:
    a, b = await make_user(session), await make_user(session)
    await make_dm(session, a, b)

    session.add(Conversation(type=ConversationType.DIRECT, direct_key=f"{a.id}:{b.id}", avatar_color="A100"))
    with pytest.raises(IntegrityError, match="UNIQUE constraint failed: conversations.direct_key"):
        await session.flush()


async def test_groups_may_share_null_direct_key(session: AsyncSession) -> None:
    session.add_all(
        [
            Conversation(type=ConversationType.GROUP, name="A", avatar_color="A100"),
            Conversation(type=ConversationType.GROUP, name="B", avatar_color="A100"),
        ]
    )
    await session.flush()

    assert await count(session, Conversation) == 2


@pytest.mark.parametrize(
    ("conversation_type", "direct_key", "name", "constraint"),
    [
        (ConversationType.DIRECT, None, None, "direct_key_matches_type"),
        (ConversationType.GROUP, "1:2", "G", "direct_key_matches_type"),
        (ConversationType.GROUP, None, None, "group_has_name"),
    ],
)
async def test_conversation_shape_checks(
    session: AsyncSession,
    conversation_type: ConversationType,
    direct_key: str | None,
    name: str | None,
    constraint: str,
) -> None:
    session.add(Conversation(type=conversation_type, direct_key=direct_key, name=name, avatar_color="A100"))
    with pytest.raises(IntegrityError, match=constraint):
        await session.flush()


# --- client_id idempotency (DB level) ---------------------------------------------


async def test_same_sender_and_client_id_is_rejected(session: AsyncSession) -> None:
    a, b = await make_user(session), await make_user(session)
    dm = await make_dm(session, a, b)
    await make_message(session, dm, a, client_id="c-1")

    with pytest.raises(IntegrityError, match="messages.sender_id, messages.client_id"):
        await make_message(session, dm, a, client_id="c-1")


async def test_same_client_id_from_different_senders_is_allowed(session: AsyncSession) -> None:
    a, b = await make_user(session), await make_user(session)
    dm = await make_dm(session, a, b)
    await make_message(session, dm, a, client_id="c-1")
    await make_message(session, dm, b, client_id="c-1")

    assert await count(session, Message) == 2


async def test_null_client_ids_never_collide(session: AsyncSession) -> None:
    a, b = await make_user(session), await make_user(session)
    dm = await make_dm(session, a, b)
    await make_message(session, dm, a, client_id=None)
    await make_message(session, dm, a, client_id=None)

    assert await count(session, Message) == 2


# --- id reuse --------------------------------------------------------------------


async def test_deleted_message_id_is_never_reused(session: AsyncSession) -> None:
    a, b = await make_user(session), await make_user(session)
    dm = await make_dm(session, a, b)
    messages = [await make_message(session, dm, a, body=f"m{i}") for i in range(3)]
    deleted_id = messages[-1].id
    await session.execute(delete(Message).where(Message.id == deleted_id))

    new_message = await make_message(session, dm, a, body="after delete")

    assert new_message.id > deleted_id


# --- cascades and SET NULL ---------------------------------------------------------


async def test_deleting_user_cascades_owned_rows_and_nulls_authorship(session: AsyncSession) -> None:
    alice, bob = await make_user(session, "Alice"), await make_user(session, "Bob")
    dm = await make_dm(session, alice, bob)
    alice_message = await make_message(session, dm, alice, body="from alice")
    bob_message = await make_message(session, dm, bob, body="from bob")
    now = utc_now()
    session.add_all(
        [
            UserSession(user_id=alice.id, token_hash="h", expires_at=now, last_used_at=now),
            UserSettings(user_id=alice.id),
            Contact(owner_id=alice.id, contact_user_id=bob.id),
            Contact(owner_id=bob.id, contact_user_id=alice.id),
            Block(blocker_id=alice.id, blocked_id=bob.id),
            Block(blocker_id=bob.id, blocked_id=alice.id),
            MessageReceipt(message_id=bob_message.id, user_id=alice.id),
            Reaction(message_id=bob_message.id, user_id=alice.id, emoji="👍"),
            Attachment(uploader_id=alice.id, file_name="a.png", mime_type="image/png", size_bytes=1, storage_path="x"),
        ]
    )
    await session.flush()

    await session.execute(delete(User).where(User.id == alice.id))

    assert await count(session, UserSession, UserSession.user_id == alice.id) == 0
    assert await count(session, UserSettings, UserSettings.user_id == alice.id) == 0
    assert await count(session, Contact) == 0  # both directions
    assert await count(session, Block) == 0  # both directions
    assert await count(session, ConversationMember, ConversationMember.user_id == alice.id) == 0
    assert await count(session, MessageReceipt, MessageReceipt.user_id == alice.id) == 0
    assert await count(session, Reaction, Reaction.user_id == alice.id) == 0
    assert await count(session, Attachment) == 0
    # SET NULL: the message survives as "Deleted user", the conversation loses its creator.
    sender = await session.scalar(select(Message.sender_id).where(Message.id == alice_message.id))
    assert sender is None
    creator = await session.scalar(select(Conversation.created_by).where(Conversation.id == dm.id))
    assert creator is None


async def test_deleting_conversation_cascades_everything_inside(session: AsyncSession) -> None:
    a, b = await make_user(session), await make_user(session)
    dm = await make_dm(session, a, b)
    message = await make_message(session, dm, a)
    session.add_all(
        [
            MessageReceipt(message_id=message.id, user_id=b.id),
            Reaction(message_id=message.id, user_id=b.id, emoji="❤️"),
            Attachment(
                message_id=message.id,
                uploader_id=a.id,
                file_name="a.png",
                mime_type="image/png",
                size_bytes=1,
                storage_path="x",
            ),
        ]
    )
    await session.flush()

    await session.execute(delete(Conversation).where(Conversation.id == dm.id))

    for model in (ConversationMember, Message, MessageReceipt, Reaction, Attachment):
        assert await count(session, model) == 0, model.__name__


async def test_deleting_quoted_message_nulls_reply_to(session: AsyncSession) -> None:
    a, b = await make_user(session), await make_user(session)
    dm = await make_dm(session, a, b)
    original = await make_message(session, dm, a, body="original")
    reply = await make_message(session, dm, b, body="reply", reply_to_id=original.id)

    await session.execute(delete(Message).where(Message.id == original.id))

    assert await session.scalar(select(Message.reply_to_id).where(Message.id == reply.id)) is None


async def test_watermark_survives_deleting_its_message(session: AsyncSession) -> None:
    """No FK on last_read_message_id: the disappearing-message sweeper can't reset it."""
    a, b = await make_user(session), await make_user(session)
    dm = await make_dm(session, a, b)
    message = await make_message(session, dm, a)
    member = await session.get(ConversationMember, (dm.id, b.id))
    assert member is not None
    member.last_read_message_id = message.id
    await session.flush()

    await session.execute(delete(Message).where(Message.id == message.id))

    watermark = await session.scalar(
        select(ConversationMember.last_read_message_id).where(
            ConversationMember.conversation_id == dm.id, ConversationMember.user_id == b.id
        )
    )
    assert watermark == message.id


# --- other CHECKs -------------------------------------------------------------------


async def test_self_contact_is_rejected(session: AsyncSession) -> None:
    user = await make_user(session)
    session.add(Contact(owner_id=user.id, contact_user_id=user.id))
    with pytest.raises(IntegrityError, match="ck_contacts_not_self"):
        await session.flush()


async def test_self_block_is_rejected(session: AsyncSession) -> None:
    user = await make_user(session)
    session.add(Block(blocker_id=user.id, blocked_id=user.id))
    with pytest.raises(IntegrityError, match="ck_blocks_not_self"):
        await session.flush()


async def test_read_without_delivered_is_rejected(session: AsyncSession) -> None:
    a, b = await make_user(session), await make_user(session)
    message = await make_message(session, await make_dm(session, a, b), a)
    session.add(MessageReceipt(message_id=message.id, user_id=b.id, delivered_at=None, read_at=utc_now()))
    with pytest.raises(IntegrityError, match="read_implies_delivered"):
        await session.flush()


async def test_removed_member_must_have_history_end(session: AsyncSession) -> None:
    a, b = await make_user(session), await make_user(session)
    dm = await make_dm(session, a, b)
    member = await session.get(ConversationMember, (dm.id, b.id))
    assert member is not None
    member.left_at = utc_now()  # history_end_id left NULL
    with pytest.raises(IntegrityError, match="left_matches_history_end"):
        await session.flush()
