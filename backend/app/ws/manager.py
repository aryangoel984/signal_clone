"""Open WebSocket connections per user (PLAN section 3, "Connection manager").

Everything runs on one asyncio event loop: connect/disconnect never await between
reading and changing the dict, so no locks are needed. One process only (--workers 1).
"""

import asyncio
import logging
from collections import defaultdict
from collections.abc import Iterable
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)

SEND_TIMEOUT_S = 5


class ConnectionManager:
    def __init__(self) -> None:
        self._sockets: defaultdict[int, set[WebSocket]] = defaultdict(set)
        self.always_online: set[int] = set()  # demo bots

    def connect(self, user_id: int, websocket: WebSocket) -> bool:
        """Registers a socket. Returns True if this is the user's first one (they just came online)."""
        first = not self._sockets[user_id]
        self._sockets[user_id].add(websocket)
        return first

    def disconnect(self, user_id: int, websocket: WebSocket) -> bool:
        """Unregisters a socket. Returns True if it was the user's last one (they went offline)."""
        sockets = self._sockets.get(user_id)
        if not sockets or websocket not in sockets:
            return False
        sockets.discard(websocket)
        if sockets:
            return False
        del self._sockets[user_id]
        return True

    def is_online(self, user_id: int) -> bool:
        return user_id in self.always_online or bool(self._sockets.get(user_id))

    def has_socket(self, user_id: int) -> bool:
        return bool(self._sockets.get(user_id))

    async def send(self, user_id: int, event: dict[str, Any]) -> None:
        await self.send_many([user_id], event)

    async def send_many(self, user_ids: Iterable[int], event: dict[str, Any]) -> None:
        """Fan out concurrently; a socket that errors or is too slow is dropped, never awaited forever."""
        targets = [(user_id, ws) for user_id in set(user_ids) for ws in list(self._sockets.get(user_id, ()))]
        results = await asyncio.gather(
            *(asyncio.wait_for(ws.send_json(event), SEND_TIMEOUT_S) for _, ws in targets), return_exceptions=True
        )
        for (user_id, ws), result in zip(targets, results, strict=True):
            if isinstance(result, BaseException):
                logger.info("Dropping socket of user %s: %r", user_id, result)
                self.disconnect(user_id, ws)
