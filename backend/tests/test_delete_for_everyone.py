from datetime import timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import update

from app.core.db import Database
from app.core.time import utc_now
from app.models import Message
from app.seed import run_seed
from tests.helpers import ALEX, DANIEL, PRIYA, chat, chat_id, login, messages, send


@pytest.fixture
async def alex(client: AsyncClient, database: Database) -> dict[str, str]:
    await run_seed(database)
    return await login(client, ALEX)


async def delete(client: AsyncClient, headers: dict[str, str], message_id: int) -> int:
    return (await client.delete(f"/api/v1/messages/{message_id}", headers=headers)).status_code


async def find(client: AsyncClient, headers: dict[str, str], conversation_id: int, message_id: int) -> dict[str, Any]:
    items = (await messages(client, headers, conversation_id, limit=100))["items"]
    return next(m for m in items if m["id"] == message_id)


async def age(database: Database, message_id: int, hours: float) -> None:
    async with database.session_factory() as session:
        await session.execute(
            update(Message).where(Message.id == message_id).values(created_at=utc_now() - timedelta(hours=hours))
        )
        await session.commit()


async def test_sender_deletes_and_everyone_sees_a_tombstone(client: AsyncClient, alex: dict[str, str]) -> None:
    dm = await chat_id(client, alex, "Priya Sharma")
    original = (await send(client, alex, dm, "Oops, wrong chat", "del-0001")).json()
    priya = await login(client, PRIYA)
    await client.put(f"/api/v1/messages/{original['id']}/reaction", headers=priya, json={"emoji": "😂"})
    reply = (
        await client.post(
            f"/api/v1/conversations/{dm}/messages",
            headers=priya,
            json={"client_id": "del-0002", "body": "What?", "reply_to_id": original["id"]},
        )
    ).json()

    assert await delete(client, alex, original["id"]) == 204

    for viewer in (alex, priya):
        tombstone = await find(client, viewer, dm, original["id"])
        assert tombstone["deleted"] is True
        assert tombstone["text"] == "This message was deleted"
        assert tombstone["reactions"] == [] and tombstone["quote"] is None and tombstone["status"] is None
        quoting = await find(client, viewer, dm, reply["id"])
        assert quoting["reply_to_id"] == original["id"] and quoting["quote"] is None  # "Original message not found"
    assert await delete(client, alex, original["id"]) == 204  # idempotent


async def test_only_the_sender_can_delete(client: AsyncClient, alex: dict[str, str]) -> None:
    dm = await chat_id(client, alex, "Priya Sharma")
    sent = (await send(client, alex, dm, "Mine", "del-0003")).json()

    assert await delete(client, await login(client, PRIYA), sent["id"]) == 403
    assert await delete(client, await login(client, DANIEL), sent["id"]) == 404  # not his chat
    assert await delete(client, alex, 999999) == 404
    assert (await find(client, alex, dm, sent["id"]))["deleted"] is False


async def test_delete_window_is_24_hours(client: AsyncClient, alex: dict[str, str], database: Database) -> None:
    dm = await chat_id(client, alex, "Priya Sharma")
    recent = (await send(client, alex, dm, "Recent", "del-0004")).json()
    old = (await send(client, alex, dm, "Old", "del-0005")).json()
    await age(database, recent["id"], 23.5)
    await age(database, old["id"], 24.5)

    assert await delete(client, alex, recent["id"]) == 204
    response = await client.delete(f"/api/v1/messages/{old['id']}", headers=alex)
    assert response.status_code == 403
    assert response.json() == {"detail": "Messages can only be deleted for everyone within 24 hours of sending"}


async def test_removed_member_cannot_delete(client: AsyncClient, alex: dict[str, str]) -> None:
    trip = await chat_id(client, alex, "Weekend Trip")
    daniel = await login(client, DANIEL)
    his = next(m for m in (await messages(client, daniel, trip))["items"] if m["sender_name"] is None and m["kind"] == "text")

    assert await delete(client, daniel, his["id"]) == 403  # removed: read-only history


async def test_preview_and_unread_count(client: AsyncClient, alex: dict[str, str]) -> None:
    dm = await chat_id(client, alex, "Priya Sharma")
    priya = await login(client, PRIYA)
    unread_before = (await chat(client, priya, "Alex Rivera"))["unread_count"]
    sent = (await send(client, alex, dm, "Unread then deleted", "del-0006")).json()
    assert (await chat(client, priya, "Alex Rivera"))["unread_count"] == unread_before + 1

    await delete(client, alex, sent["id"])

    for viewer, title in ((priya, "Alex Rivera"), (alex, "Priya Sharma")):
        row = await chat(client, viewer, title)
        assert row["last_message"]["text"] == "This message was deleted"
        assert row["last_message"]["status"] is None
    assert (await chat(client, priya, "Alex Rivera"))["unread_count"] == unread_before


async def test_deleted_message_cannot_be_reacted_to_replied_to_or_inspected(client: AsyncClient, alex: dict[str, str]) -> None:
    dm = await chat_id(client, alex, "Priya Sharma")
    sent = (await send(client, alex, dm, "Gone soon", "del-0007")).json()
    await delete(client, alex, sent["id"])
    priya = await login(client, PRIYA)

    react = await client.put(f"/api/v1/messages/{sent['id']}/reaction", headers=priya, json={"emoji": "❤️"})
    reply = await client.post(
        f"/api/v1/conversations/{dm}/messages", headers=priya, json={"client_id": "del-0008", "body": "x", "reply_to_id": sent["id"]}
    )
    details = await client.get(f"/api/v1/messages/{sent['id']}/receipts", headers=alex)
    assert (react.status_code, reply.status_code, details.status_code) == (404, 400, 404)


async def test_blocked_sender_tombstone_stays_hidden(client: AsyncClient, alex: dict[str, str]) -> None:
    dm = await chat_id(client, alex, "Priya Sharma")
    priya = await login(client, PRIYA)
    priya_id = (await client.get("/api/v1/users/me", headers=priya)).json()["id"]
    await client.put(f"/api/v1/blocks/{priya_id}", headers=alex)
    hidden = (await send(client, priya, dm, "Sent while blocked", "del-0009")).json()

    assert await delete(client, priya, hidden["id"]) == 204

    items = (await messages(client, alex, dm, limit=100))["items"]
    assert all(m["id"] != hidden["id"] for m in items)  # still invisible to the blocker, deleted or not
