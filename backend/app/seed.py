"""Demo data seed.

    python -m app.seed           # idempotent: adds whatever is missing, changes nothing that exists
    python -m app.seed --reset   # DESTRUCTIVE: drops every table and seeds from scratch

Idempotency: users are matched by phone, DMs by direct_key, groups by (name, creator),
contacts/blocks/members by primary key. A conversation's messages are seeded only if it
has none yet, so system messages (NULL client_id) are never duplicated.
"""

import argparse
import asyncio
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.avatar_colors import avatar_color_for
from app.core.config import get_settings
from app.core.db import Database, create_database, drop_db, init_db
from app.core.time import utc_now
from app.models import (
    Base,
    Block,
    Contact,
    Conversation,
    ConversationMember,
    Message,
    MessageReceipt,
    User,
    UserSettings,
)
from app.models.enums import ConversationType, MessageKind
from app.seed_data import BLOCKS, CONTACTS, CONVERSATIONS, USERS, Event, Say, SeedConversation, SeedMember

DELIVERY_DELAY = timedelta(seconds=2)
READ_DELAY = timedelta(seconds=5)


@dataclass
class _SeededConversation:
    spec: SeedConversation
    conversation: Conversation
    members: dict[str, ConversationMember]  # by seed user key


async def run_seed(database: Database, *, reset: bool = False) -> None:
    if reset:
        await drop_db(database)
    await init_db(database)

    async with database.session_factory() as session:
        now = utc_now()
        users = await _ensure_users(session, now)
        await _ensure_contacts(session, users)
        blocks = await _ensure_blocks(session, users, now)

        needs_messages: list[_SeededConversation] = []
        for spec in CONVERSATIONS:
            seeded = await _ensure_conversation(session, spec, users, now)
            if not await _has_messages(session, seeded.conversation):
                needs_messages.append(seeded)

        messages = await _insert_messages(session, needs_messages, users, now)
        for seeded in needs_messages:
            _apply_read_state(session, seeded, messages[seeded.spec.key], users, blocks)

        await session.commit()


async def _ensure_users(session: AsyncSession, now: datetime) -> dict[str, User]:
    users: dict[str, User] = {}
    for seed_user in USERS:
        user = await session.scalar(select(User).where(User.phone_number == seed_user.phone))
        if user is None:
            user = User(
                phone_number=seed_user.phone,
                username=seed_user.username,
                display_name=seed_user.display_name,
                about=seed_user.about,
                avatar_color=avatar_color_for(seed_user.phone),
                last_seen_at=now - timedelta(minutes=seed_user.last_seen_minutes_ago),
            )
            session.add(user)
            await session.flush()
        if await session.get(UserSettings, user.id) is None:
            session.add(UserSettings(user_id=user.id, read_receipts_enabled=seed_user.read_receipts))
        users[seed_user.key] = user
    return users


async def _ensure_contacts(session: AsyncSession, users: dict[str, User]) -> None:
    for seed_contact in CONTACTS:
        owner_id, contact_id = users[seed_contact.owner].id, users[seed_contact.contact].id
        if await session.get(Contact, (owner_id, contact_id)) is None:
            session.add(Contact(owner_id=owner_id, contact_user_id=contact_id, nickname=seed_contact.nickname))


async def _ensure_blocks(
    session: AsyncSession, users: dict[str, User], now: datetime
) -> dict[tuple[int, int], datetime]:
    """Returns {(blocker_id, blocked_id): blocked_at} for deriving receipts."""
    blocks: dict[tuple[int, int], datetime] = {}
    for seed_block in BLOCKS:
        key = (users[seed_block.blocker].id, users[seed_block.blocked].id)
        block = await session.get(Block, key)
        if block is None:
            block = Block(blocker_id=key[0], blocked_id=key[1], created_at=now - timedelta(minutes=seed_block.minutes_ago))
            session.add(block)
        blocks[key] = block.created_at
    return blocks


async def _ensure_conversation(
    session: AsyncSession, spec: SeedConversation, users: dict[str, User], now: datetime
) -> _SeededConversation:
    creator = users[spec.creator]
    created_at = now - timedelta(minutes=spec.script[0].minutes_ago)

    if spec.type is ConversationType.DIRECT:
        a, b = (users[member.user].id for member in spec.members)
        direct_key = f"{min(a, b)}:{max(a, b)}"
        conversation = await session.scalar(select(Conversation).where(Conversation.direct_key == direct_key))
        new_conversation = Conversation(
            type=ConversationType.DIRECT,
            direct_key=direct_key,
            avatar_color=avatar_color_for(direct_key),
            created_by=creator.id,
            created_at=created_at,
        )
    else:
        conversation = await session.scalar(
            select(Conversation).where(
                Conversation.type == ConversationType.GROUP,
                Conversation.name == spec.name,
                Conversation.created_by == creator.id,
            )
        )
        new_conversation = Conversation(
            type=ConversationType.GROUP,
            name=spec.name,
            avatar_color=avatar_color_for(f"group:{spec.name}"),
            created_by=creator.id,
            created_at=created_at,
        )

    if conversation is None:
        conversation = new_conversation
        session.add(conversation)
        await session.flush()

    members: dict[str, ConversationMember] = {}
    for seed_member in spec.members:
        user_id = users[seed_member.user].id
        member = await session.get(ConversationMember, (conversation.id, user_id))
        if member is None:
            member = ConversationMember(
                conversation_id=conversation.id,
                user_id=user_id,
                role=seed_member.role,
                joined_at=conversation.created_at,
            )
            session.add(member)
        members[seed_member.user] = member
    await session.flush()
    return _SeededConversation(spec, conversation, members)


async def _has_messages(session: AsyncSession, conversation: Conversation) -> bool:
    query = select(exists().where(Message.conversation_id == conversation.id))
    return bool(await session.scalar(query))


async def _insert_messages(
    session: AsyncSession, pending: list[_SeededConversation], users: dict[str, User], now: datetime
) -> dict[str, list[Message]]:
    """Inserts all script items in global time order so message ids increase with
    created_at everywhere. Returns messages per conversation, aligned with spec.script."""
    timeline = sorted(
        (
            (now - timedelta(minutes=item.minutes_ago), order, seeded, index)
            for order, seeded in enumerate(pending)
            for index, item in enumerate(seeded.spec.script)
        ),
        key=lambda entry: (entry[0], entry[1], entry[3]),
    )

    by_conversation: dict[str, dict[int, Message]] = defaultdict(dict)
    for created_at, _, seeded, index in timeline:
        item = seeded.spec.script[index]
        if isinstance(item, Say):
            message = Message(
                conversation_id=seeded.conversation.id,
                sender_id=users[item.sender].id,
                kind=MessageKind.TEXT,
                body=item.text,
                client_id=f"seed:{seeded.spec.key}:{index:03d}",
                created_at=created_at,
            )
        else:
            message = Message(
                conversation_id=seeded.conversation.id,
                sender_id=users[item.actor].id,
                kind=MessageKind.SYSTEM,
                body=item.event,
                system_data={
                    "event": item.event,
                    "actor_id": users[item.actor].id,
                    "target_ids": [users[target].id for target in item.targets],
                    # group names are reconstructed from these when a viewer blocked a renamer
                    **({"name": seeded.spec.name} if item.event == "group_created" and seeded.spec.name else {}),
                },
                created_at=created_at,
            )
        session.add(message)
        await session.flush()
        by_conversation[seeded.spec.key][index] = message

    return {key: [messages[i] for i in sorted(messages)] for key, messages in by_conversation.items()}


def _apply_read_state(
    session: AsyncSession,
    seeded: _SeededConversation,
    messages: list[Message],
    users: dict[str, User],
    blocks: dict[tuple[int, int], datetime],
) -> None:
    """Derives history ranges, receipts, watermarks and last_message_at from the spec."""
    spec, conversation = seeded.spec, seeded.conversation
    conversation.last_message_at = max(message.created_at for message in messages)
    labelled = {
        item.label: messages[index]
        for index, item in enumerate(spec.script)
        if isinstance(item, Event) and item.label is not None
    }
    read_receipts_on = {seed_user.key: seed_user.read_receipts for seed_user in USERS}

    for seed_member in spec.members:
        member = seeded.members[seed_member.user]
        if seed_member.added_by is not None:
            added = labelled[seed_member.added_by]
            member.history_start_id = added.id - 1  # they see the "added you" message onwards
            member.joined_at = added.created_at
        if seed_member.removed_by is not None:
            removed = labelled[seed_member.removed_by]
            member.history_end_id = removed.id  # they see their own removal, nothing after
            member.left_at = removed.created_at

        visible = [
            message
            for message in messages
            if message.id > member.history_start_id
            and (member.history_end_id is None or message.id <= member.history_end_id)
        ]
        _check_tails(spec, seed_member, visible, member.user_id)
        delivered_count = len(visible) - seed_member.undelivered_tail
        read_count = len(visible) - seed_member.unread_tail

        for position, message in enumerate(visible):
            if message.kind is not MessageKind.TEXT or message.sender_id == member.user_id:
                continue
            blocked_at = blocks.get((member.user_id, message.sender_id or 0))
            if blocked_at is not None and message.created_at >= blocked_at:
                continue  # never delivered to someone who blocked the sender (PLAN 7.2)
            delivered = position < delivered_count
            read = delivered and position < read_count and read_receipts_on[seed_member.user]
            session.add(
                MessageReceipt(
                    message_id=message.id,
                    user_id=member.user_id,
                    delivered_at=message.created_at + DELIVERY_DELAY if delivered else None,
                    read_at=message.created_at + READ_DELAY if read else None,
                    created_at=message.created_at,
                )
            )

        last_read_id = visible[read_count - 1].id if read_count > 0 else 0
        own_last_id = max((m.id for m in visible if m.sender_id == member.user_id), default=0)
        # Sending a message implies having read everything before it.
        member.last_read_message_id = max(last_read_id, own_last_id, member.history_start_id)


def _check_tails(spec: SeedConversation, seed_member: SeedMember, visible: list[Message], user_id: int) -> None:
    name = f"{spec.key}/{seed_member.user}"
    if seed_member.undelivered_tail > seed_member.unread_tail:
        raise ValueError(f"{name}: a message can't be read before it is delivered")
    if seed_member.unread_tail > len(visible):
        raise ValueError(f"{name}: unread_tail is longer than the visible history")
    tail = visible[len(visible) - seed_member.unread_tail :]
    if any(message.sender_id == user_id for message in tail):
        raise ValueError(f"{name}: unread/undelivered tails may only contain other people's messages")


async def table_counts(database: Database) -> dict[str, int]:
    async with database.session_factory() as session:
        return {
            table.name: (await session.execute(select(func.count()).select_from(table))).scalar_one()
            for table in Base.metadata.sorted_tables
        }


async def _main(reset: bool) -> None:
    database = create_database(get_settings().database_url)
    try:
        await run_seed(database, reset=reset)
        counts = await table_counts(database)
        print("Seed complete:", ", ".join(f"{name}={count}" for name, count in counts.items()))
    finally:
        await database.engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the Signal clone database with demo data.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="DESTRUCTIVE: drop all tables and reseed from scratch. Never use on boot.",
    )
    args = parser.parse_args()
    asyncio.run(_main(args.reset))


if __name__ == "__main__":
    main()
