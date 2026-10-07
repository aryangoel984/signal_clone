from collections import defaultdict

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import Database
from app.models import Conversation, ConversationMember, Message, MessageReceipt, User, UserSettings
from app.models.enums import ConversationType, MessageKind, MessageStatus
from app.seed import run_seed, table_counts
from app.seed_data import DEMO_PHONE
from app.services.message_queries import aggregate_status, last_visible_message, unread_count, visible_to


@pytest.fixture
async def seeded(database: Database) -> Database:
    await run_seed(database)
    return database


async def user_by_phone(session: AsyncSession, phone: str) -> User:
    return (await session.execute(select(User).where(User.phone_number == phone))).scalar_one()


async def user_by_name(session: AsyncSession, name: str) -> User:
    return (await session.execute(select(User).where(User.display_name == name))).scalar_one()


async def group(session: AsyncSession, name: str) -> Conversation:
    return (await session.execute(select(Conversation).where(Conversation.name == name))).scalar_one()


async def membership(session: AsyncSession, conversation: Conversation, user: User) -> ConversationMember:
    member = await session.get(ConversationMember, (conversation.id, user.id))
    assert member is not None
    return member


async def test_seed_twice_creates_no_duplicates(seeded: Database) -> None:
    first = await table_counts(seeded)
    await run_seed(seeded)

    assert await table_counts(seeded) == first


async def test_reset_reproduces_the_same_data(seeded: Database) -> None:
    first = await table_counts(seeded)
    await run_seed(seeded, reset=True)

    assert await table_counts(seeded) == first


async def test_minimum_demo_data(seeded: Database, settings: Settings, session: AsyncSession) -> None:
    counts = await table_counts(seeded)
    conversation_types = (await session.execute(select(Conversation.type))).scalars().all()

    assert counts["users"] >= 8
    assert conversation_types.count(ConversationType.DIRECT) >= 5
    assert conversation_types.count(ConversationType.GROUP) >= 2
    phones = set((await session.execute(select(User.phone_number))).scalars())
    assert set(settings.demo_bot_phones) <= phones


async def test_receipts_agree_with_watermarks(seeded: Database, session: AsyncSession) -> None:
    members = (await session.execute(select(ConversationMember))).scalars().all()
    receipts_on = dict((await session.execute(select(UserSettings.user_id, UserSettings.read_receipts_enabled))).all())

    for member in members:
        rows = (
            await session.execute(
                select(Message.id, MessageReceipt.delivered_at, MessageReceipt.read_at)
                .join(MessageReceipt, MessageReceipt.message_id == Message.id)
                .where(Message.conversation_id == member.conversation_id, MessageReceipt.user_id == member.user_id)
            )
        ).all()
        for message_id, delivered_at, read_at in rows:
            assert read_at is None or delivered_at is not None
            if receipts_on[member.user_id]:
                assert (read_at is not None) == (message_id <= member.last_read_message_id), (member, message_id)
            else:
                assert read_at is None  # PLAN 7.4: nothing is recorded with receipts off


async def test_demo_user_unread_counts(seeded: Database, session: AsyncSession) -> None:
    alex = await user_by_phone(session, DEMO_PHONE)
    sofia = await user_by_name(session, "Sofia Rossi")
    sofia_dm = (
        await session.execute(
            select(Conversation).where(Conversation.direct_key == f"{min(alex.id, sofia.id)}:{max(alex.id, sofia.id)}")
        )
    ).scalar_one()
    expected = {sofia_dm.id: 3, (await group(session, "Book Club")).id: 5}

    memberships = (await session.execute(select(ConversationMember).where(ConversationMember.user_id == alex.id))).scalars()
    actual = {member.conversation_id: await unread_count(session, member) for member in memberships}

    assert {cid: n for cid, n in actual.items() if n} == expected


async def test_demo_user_sees_every_outgoing_status(seeded: Database, session: AsyncSession) -> None:
    alex = await user_by_phone(session, DEMO_PHONE)
    receipts = (
        await session.execute(
            select(MessageReceipt)
            .join(Message, Message.id == MessageReceipt.message_id)
            .where(Message.sender_id == alex.id, Message.kind == MessageKind.TEXT)
        )
    ).scalars()
    by_message: dict[int, list[MessageReceipt]] = defaultdict(list)
    for receipt in receipts:
        by_message[receipt.message_id].append(receipt)

    statuses = {aggregate_status(message_receipts) for message_receipts in by_message.values()}

    assert statuses == {MessageStatus.SENT, MessageStatus.DELIVERED, MessageStatus.READ}


async def test_ids_follow_time_and_last_message_at_matches(seeded: Database, session: AsyncSession) -> None:
    for conversation in (await session.execute(select(Conversation))).scalars():
        messages = (
            await session.execute(select(Message).where(Message.conversation_id == conversation.id).order_by(Message.id))
        ).scalars().all()
        times = [message.created_at for message in messages]
        assert times == sorted(times)
        assert conversation.last_message_at == times[-1]


async def test_added_member_sees_nothing_before_being_added(seeded: Database, session: AsyncSession) -> None:
    trip = await group(session, "Weekend Trip")
    emma = await membership(session, trip, await user_by_name(session, "Emma Larsen"))

    first_visible = (
        await session.execute(select(Message).where(visible_to(emma)).order_by(Message.id).limit(1))
    ).scalar_one()

    assert first_visible.body == "member_added"
    assert await unread_count(session, emma) == 0


async def test_removed_member_unread_and_preview_stay_in_range(seeded: Database, session: AsyncSession) -> None:
    trip = await group(session, "Weekend Trip")
    daniel = await membership(session, trip, await user_by_name(session, "Daniel Okafor"))
    newest_in_group = await session.scalar(select(Message.id).where(Message.conversation_id == trip.id).order_by(Message.id.desc()))

    preview = await last_visible_message(session, daniel)

    assert daniel.history_end_id is not None and daniel.left_at is not None
    assert await unread_count(session, daniel) == 0
    assert preview is not None
    assert daniel.history_start_id < preview.id <= daniel.history_end_id
    assert preview.body == "member_removed"  # his own removal is the last thing he sees
    assert newest_in_group is not None and newest_in_group > daniel.history_end_id


async def test_blocked_spammer_has_only_pre_block_messages(seeded: Database, session: AsyncSession) -> None:
    alex = await user_by_phone(session, DEMO_PHONE)
    spammer = await user_by_name(session, "Crypto Deals")
    messages = (await session.execute(select(Message).where(Message.sender_id == spammer.id))).scalars().all()
    receipts = (
        await session.execute(select(MessageReceipt).where(MessageReceipt.message_id.in_([m.id for m in messages])))
    ).scalars().all()

    assert len(messages) == 2
    assert {receipt.user_id for receipt in receipts} == {alex.id}
