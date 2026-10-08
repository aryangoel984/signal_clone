"""Turns committed changes into WebSocket events (PLAN section 3).

Services call these methods *after* their commit, so clients never hear about data that
was rolled back. Each method opens its own short database session.
"""

import asyncio
import logging
from collections import defaultdict
from collections.abc import Awaitable, Callable, Coroutine
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.time import utc_now
from app.models import Block, Contact, ConversationMember, Message, User, UserSettings
from app.services import receipt_service
from app.services.message_queries import statuses_for
from app.ws.events import GroupUpdated, MessageNew, MessageStatusChanged, PresenceUpdate, StatusUpdate, Typing, envelope
from app.ws.manager import ConnectionManager

logger = logging.getLogger(__name__)

MessageHook = Callable[[Message], Awaitable[None]]


class TypingNotAllowedError(Exception):
    pass


class Realtime:
    def __init__(self, manager: ConnectionManager, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.manager = manager
        self._sessions = session_factory
        self.message_hooks: list[MessageHook] = []  # e.g. the demo bots
        self._background: set[asyncio.Task[None]] = set()

    def spawn(self, work: Coroutine[object, object, None]) -> None:
        """Runs follow-up work (e.g. disconnect cleanup) without tying it to the caller, so a
        cancelled WebSocket handler can't abort it halfway. Tracked until done; awaited on shutdown."""
        task = asyncio.create_task(work)
        self._background.add(task)
        task.add_done_callback(self._background.discard)

    async def shutdown(self) -> None:
        await asyncio.gather(*self._background, return_exceptions=True)

    # --- presence --------------------------------------------------------------------------

    def is_online(self, user_id: int) -> bool:
        return self.manager.is_online(user_id)

    async def went_online(self, user_id: int) -> None:
        await self._broadcast_presence(user_id, online=True, last_seen_at=None)

    async def went_offline(self, user_id: int) -> None:
        now = utc_now()
        async with self._sessions() as session:
            await session.execute(update(User).where(User.id == user_id).values(last_seen_at=now))
            await session.commit()
        await self._broadcast_presence(user_id, online=False, last_seen_at=now)

    async def _broadcast_presence(self, user_id: int, *, online: bool, last_seen_at: datetime | None) -> None:
        """Audience: everyone who shares an active conversation with the user or has them as a contact."""
        async with self._sessions() as session:
            my_conversations = select(ConversationMember.conversation_id).where(
                ConversationMember.user_id == user_id, ConversationMember.left_at.is_(None)
            )
            co_members = select(ConversationMember.user_id).where(
                ConversationMember.conversation_id.in_(my_conversations), ConversationMember.left_at.is_(None)
            )
            has_me_as_contact = select(Contact.owner_id).where(Contact.contact_user_id == user_id)
            audience = set((await session.execute(co_members)).scalars()) | set(
                (await session.execute(has_me_as_contact)).scalars()
            )
        audience.discard(user_id)
        await self.manager.send_many(
            audience, envelope("presence.update", PresenceUpdate(user_id=user_id, online=online, last_seen_at=last_seen_at))
        )

    # --- messages and receipts -----------------------------------------------------------

    async def message_created(self, message_id: int, extra_recipient_ids: tuple[int, ...] = ()) -> None:
        """message.new to every active member (worded for each), then mark it delivered for
        recipients whose socket received it and tell the sender. `extra_recipient_ids` adds
        people who are no longer members but must see this one (their own removal)."""
        from app.services.message_service import serialize  # local import: message_service imports this module's types

        async with self._sessions() as session:
            message = await session.get(Message, message_id)
            if message is None:
                return
            rows = await session.execute(
                select(User)
                .join(ConversationMember, ConversationMember.user_id == User.id)
                .where(
                    ConversationMember.conversation_id == message.conversation_id,
                    (ConversationMember.left_at.is_(None)) | (ConversationMember.user_id.in_(extra_recipient_ids)),
                )
            )
            members = list(rows.scalars())
            blocked_sender = set(
                (
                    await session.execute(select(Block.blocker_id).where(Block.blocked_id == message.sender_id))
                ).scalars()
            )
            pushed: list[int] = []
            for member in members:
                if member.id in blocked_sender or not self.manager.has_socket(member.id):
                    continue  # blocked users never receive it (PLAN 7.2)
                out = (await serialize(session, member, [message]))[0]
                await self.manager.send(member.id, envelope("message.new", MessageNew(conversation_id=message.conversation_id, message=out)))
                if member.id != message.sender_id:
                    pushed.append(member.id)
            delivered = await receipt_service.mark_delivered(session, pushed, message.id)

        await self.statuses_changed(delivered)
        for hook in self.message_hooks:
            try:
                await hook(message)
            except Exception:  # a hook must never break sending
                logger.exception("message hook failed")

    async def deliver_pending(self, user_id: int) -> None:
        """A user connected: everything waiting for them is now delivered."""
        async with self._sessions() as session:
            changed = await receipt_service.mark_all_delivered(session, user_id)
        await self.statuses_changed(changed)

    async def statuses_changed(self, message_ids: list[int]) -> None:
        """message.status to the senders of these messages, with their new aggregate status."""
        if not message_ids:
            return
        async with self._sessions() as session:
            rows = await session.execute(
                select(Message.id, Message.sender_id, Message.conversation_id).where(Message.id.in_(message_ids))
            )
            by_sender: defaultdict[int, defaultdict[int, list[int]]] = defaultdict(lambda: defaultdict(list))
            for message_id, sender_id, conversation_id in rows:
                if sender_id is not None and self.manager.has_socket(sender_id):
                    by_sender[sender_id][conversation_id].append(message_id)
            for sender_id, conversations in by_sender.items():
                sender = await session.get(User, sender_id)
                if sender is None:
                    continue
                for conversation_id, ids in conversations.items():
                    statuses = await statuses_for(session, sender, ids)
                    updates = [StatusUpdate(message_id=i, status=s) for i, s in statuses.items()]
                    await self.manager.send(
                        sender_id,
                        envelope("message.status", MessageStatusChanged(conversation_id=conversation_id, updates=updates)),
                    )

    # --- groups ------------------------------------------------------------------------------

    async def group_updated(
        self,
        conversation_id: int,
        change: str,
        actor_id: int,
        target_ids: list[int],
        extra_recipient_ids: tuple[int, ...] = (),
    ) -> None:
        """group.updated to active members plus e.g. someone just removed; clients refetch."""
        async with self._sessions() as session:
            members = (
                await session.execute(
                    select(ConversationMember.user_id).where(
                        ConversationMember.conversation_id == conversation_id, ConversationMember.left_at.is_(None)
                    )
                )
            ).scalars()
            recipients = set(members) | set(extra_recipient_ids)
        event = GroupUpdated(conversation_id=conversation_id, change=change, actor_id=actor_id, target_ids=target_ids)
        await self.manager.send_many(recipients, envelope("group.updated", event))

    # --- typing ------------------------------------------------------------------------------

    async def typing(self, user_id: int, conversation_id: int, *, started: bool) -> None:
        """Relays typing to the other active members. Only active members with typing
        indicators on may type; members who blocked the typist don't see it."""
        async with self._sessions() as session:
            member = await session.get(ConversationMember, (conversation_id, user_id))
            if member is None or member.left_at is not None:
                raise TypingNotAllowedError("Not a member of this conversation")
            settings = await session.get(UserSettings, user_id)
            if settings is not None and not settings.typing_indicators_enabled:
                return
            blocked_me = select(Block.blocker_id).where(Block.blocked_id == user_id)
            # People who turned typing indicators off don't see others' either (Signal).
            not_watching = select(UserSettings.user_id).where(UserSettings.typing_indicators_enabled.is_(False))
            audience = (
                await session.execute(
                    select(ConversationMember.user_id).where(
                        ConversationMember.conversation_id == conversation_id,
                        ConversationMember.left_at.is_(None),
                        ConversationMember.user_id != user_id,
                        ConversationMember.user_id.not_in(blocked_me),
                        ConversationMember.user_id.not_in(not_watching),
                    )
                )
            ).scalars()
            recipients = list(audience)
        event = envelope("typing.start" if started else "typing.stop", Typing(conversation_id=conversation_id, user_id=user_id))
        await self.manager.send_many(recipients, event)

