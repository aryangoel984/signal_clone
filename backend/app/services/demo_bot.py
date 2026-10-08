"""Demo bots (PLAN section 8): seeded users who react to messages so the app can be
demoed with one browser. They go through the same services as real users, so every
normal event (message.status, typing, message.new) fires."""

import asyncio
import itertools
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import ConversationMember, Message, User
from app.models.enums import ConversationType, MessageKind
from app.models.conversation import Conversation
from app.services import receipt_service
from app.ws.realtime import Realtime

logger = logging.getLogger(__name__)

DELIVER_AFTER_S = 0.4
READ_AFTER_S = 0.6
TYPING_AFTER_S = 0.3
REPLIES = (
    "Sounds good to me 👍",
    "Ha, love that.",
    "Tell me more!",
    "I'm a demo bot, but I'm listening 🤖",
    "Interesting! What happened next?",
    "Noted ✅",
)


def pick_reply(text: str, counter: int) -> str:
    lowered = text.lower()
    if any(word in lowered.split() for word in ("hi", "hey", "hello", "hi!", "hello!")):
        return "Hey there! 👋"
    if text.rstrip().endswith("?"):
        return "Good question 🤔"
    return REPLIES[counter % len(REPLIES)]


class DemoBots:
    def __init__(
        self,
        realtime: Realtime,
        session_factory: async_sessionmaker[AsyncSession],
        bot_phones: list[str],
        delay_scale: float,
    ) -> None:
        self._realtime = realtime
        self._sessions = session_factory
        self._phones = bot_phones
        self._scale = delay_scale
        self._bot_ids: set[int] = set()
        self._pending: dict[tuple[int, int], asyncio.Task[None]] = {}  # (bot, conversation) -> task
        self._counter = itertools.count()

    async def load(self) -> None:
        """Resolve bot phone numbers to user ids; bots always appear online."""
        async with self._sessions() as session:
            ids = (await session.execute(select(User.id).where(User.phone_number.in_(self._phones)))).scalars()
            self._bot_ids = set(ids)
        self._realtime.manager.always_online = set(self._bot_ids)

    async def on_message(self, message: Message) -> None:
        """Hook called after a message was broadcast. Returns immediately; work runs in tasks."""
        if message.kind is not MessageKind.TEXT or message.sender_id in self._bot_ids or not self._bot_ids:
            return
        async with self._sessions() as session:
            conversation = await session.get(Conversation, message.conversation_id)
            bots_here = (
                await session.execute(
                    select(ConversationMember.user_id).where(
                        ConversationMember.conversation_id == message.conversation_id,
                        ConversationMember.user_id.in_(self._bot_ids),
                        ConversationMember.left_at.is_(None),
                    )
                )
            ).scalars()
            bot_ids = list(bots_here)
        if conversation is None:
            return
        is_dm = conversation.type is ConversationType.DIRECT
        for bot_id in bot_ids:
            key = (bot_id, message.conversation_id)
            if previous := self._pending.get(key):
                previous.cancel()  # a burst of messages gets one reply
            task = asyncio.create_task(self._react(bot_id, message.conversation_id, message.id, message.body, is_dm))
            self._pending[key] = task
            task.add_done_callback(lambda done, key=key: self._forget(key, done))

    def _forget(self, key: tuple[int, int], task: asyncio.Task[None]) -> None:
        if self._pending.get(key) is task:
            del self._pending[key]
        if not task.cancelled() and task.exception() is not None:
            logger.error("demo bot failed", exc_info=task.exception())

    async def shutdown(self) -> None:
        for task in list(self._pending.values()):
            task.cancel()
        await asyncio.gather(*self._pending.values(), return_exceptions=True)

    async def _sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds * self._scale)

    async def _react(self, bot_id: int, conversation_id: int, message_id: int, text: str, is_dm: bool) -> None:
        from app.services.message_service import send_message  # local: message_service -> realtime -> hooks

        await self._sleep(DELIVER_AFTER_S)
        async with self._sessions() as session:
            delivered = await receipt_service.mark_delivered(session, [bot_id], message_id)
        await self._realtime.statuses_changed(delivered)

        await self._sleep(READ_AFTER_S)
        async with self._sessions() as session:
            bot = await session.get(User, bot_id)
            member = await session.get(ConversationMember, (conversation_id, bot_id))
            if bot is None or member is None:
                return
            read = await receipt_service.mark_read(session, bot, member, message_id)
        await self._realtime.statuses_changed(read)

        if not is_dm:
            return  # in groups bots only read, so it doesn't get noisy
        reply = pick_reply(text, next(self._counter))
        await self._sleep(TYPING_AFTER_S)
        await self._realtime.typing(bot_id, conversation_id, started=True)
        try:
            await self._sleep(min(3.0, 1.5 + len(reply) / 40))
        finally:
            await self._realtime.typing(bot_id, conversation_id, started=False)
        async with self._sessions() as session:
            bot = await session.get(User, bot_id)
            if bot is not None:
                await send_message(session, self._realtime, bot, conversation_id, f"bot-{uuid.uuid4()}", reply)
