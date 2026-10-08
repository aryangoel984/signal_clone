from typing import Any

import pytest
from httpx import AsyncClient

from app.core.db import Database
from app.seed import run_seed
from tests.helpers import ALEX, DANIEL, EMMA, PRIYA, chat_id, login, messages


@pytest.fixture
async def alex(client: AsyncClient, database: Database) -> dict[str, str]:
    await run_seed(database)
    return await login(client, ALEX)


async def reply(
    client: AsyncClient, headers: dict[str, str], conversation_id: int, reply_to_id: int, client_id: str
) -> Any:
    return await client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        headers=headers,
        json={"client_id": client_id, "body": "Replying", "reply_to_id": reply_to_id},
    )


async def first_text(client: AsyncClient, headers: dict[str, str], conversation_id: int, sender_name: str | None) -> dict[str, Any]:
    """The oldest text message from this sender (None = mine) on the latest page."""
    items = (await messages(client, headers, conversation_id))["items"]
    return next(m for m in items if m["kind"] == "text" and m["sender_name"] == sender_name)


async def find(client: AsyncClient, headers: dict[str, str], conversation_id: int, message_id: int) -> dict[str, Any]:
    items = (await messages(client, headers, conversation_id, limit=100))["items"]
    return next(m for m in items if m["id"] == message_id)


async def react(client: AsyncClient, headers: dict[str, str], message_id: int, emoji: str) -> int:
    return (await client.put(f"/api/v1/messages/{message_id}/reaction", headers=headers, json={"emoji": emoji})).status_code


# --- replies -----------------------------------------------------------------------------------


async def test_reply_carries_a_viewer_relative_quote(client: AsyncClient, alex: dict[str, str]) -> None:
    dm = await chat_id(client, alex, "Priya Sharma")
    original = await first_text(client, alex, dm, "Priya Sharma")

    response = await reply(client, alex, dm, original["id"], "reply-0001")

    assert response.status_code == 201, response.text
    sent = response.json()
    assert sent["reply_to_id"] == original["id"]
    assert sent["quote"] == {"id": original["id"], "sender_id": original["sender_id"], "author_name": "Priya Sharma", "text": original["text"]}
    priya = await login(client, PRIYA)
    assert (await find(client, priya, dm, sent["id"]))["quote"]["author_name"] == "You"


async def test_reply_must_target_a_visible_text_message_in_the_same_chat(client: AsyncClient, alex: dict[str, str]) -> None:
    dm = await chat_id(client, alex, "Priya Sharma")
    trip = await chat_id(client, alex, "Weekend Trip")
    elsewhere = await first_text(client, alex, trip, "Priya Sharma")
    system_line = (await messages(client, alex, trip))["items"][0]
    assert system_line["kind"] == "system"

    cases = (
        (dm, elsewhere["id"], "reply-0002"),  # a message from another chat
        (trip, system_line["id"], "reply-0003"),  # "You created the group."
        (dm, 999999, "reply-0004"),  # doesn't exist
    )
    for conversation_id, target, client_id in cases:
        response = await reply(client, alex, conversation_id, target, client_id)
        assert response.status_code == 400, response.text
        assert response.json() == {"detail": "Can't reply to that message"}


async def test_quote_is_hidden_from_members_who_cannot_see_the_original(client: AsyncClient, alex: dict[str, str]) -> None:
    trip = await chat_id(client, alex, "Weekend Trip")
    original = await first_text(client, alex, trip, None)  # sent before Emma was added

    sent = (await reply(client, alex, trip, original["id"], "reply-0005")).json()

    emma = await login(client, EMMA)
    seen_by_emma = await find(client, emma, trip, sent["id"])
    assert seen_by_emma["reply_to_id"] == original["id"]
    assert seen_by_emma["quote"] is None  # the UI shows "Original message not found"
    priya = await login(client, PRIYA)
    assert (await find(client, priya, trip, sent["id"]))["quote"]["author_name"] == "Alex Rivera"


# --- reactions ---------------------------------------------------------------------------------


async def test_one_reaction_per_user_replaced_then_removed(client: AsyncClient, alex: dict[str, str]) -> None:
    dm = await chat_id(client, alex, "Priya Sharma")
    message = await first_text(client, alex, dm, None)
    priya = await login(client, PRIYA)
    priya_id = (await client.get("/api/v1/users/me", headers=priya)).json()["id"]

    assert await react(client, priya, message["id"], "❤️") == 204
    assert await react(client, priya, message["id"], "👍") == 204  # replaces, doesn't add
    assert await react(client, alex, message["id"], "😂") == 204
    reactions = (await find(client, alex, dm, message["id"]))["reactions"]
    assert {(r["user_id"], r["emoji"]) for r in reactions} == {(priya_id, "👍"), (message["sender_id"], "😂")}

    assert (await client.delete(f"/api/v1/messages/{message['id']}/reaction", headers=priya)).status_code == 204
    assert (await client.delete(f"/api/v1/messages/{message['id']}/reaction", headers=priya)).status_code == 204  # idempotent
    assert [r["emoji"] for r in (await find(client, alex, dm, message["id"]))["reactions"]] == ["😂"]


@pytest.mark.parametrize("body", [{"emoji": "🦄"}, {"emoji": "hello"}, {"emoji": ""}, {}, {"emoji": "❤️", "extra": 1}])
async def test_only_the_offered_emoji_are_accepted(client: AsyncClient, alex: dict[str, str], body: dict[str, Any]) -> None:
    dm = await chat_id(client, alex, "Priya Sharma")
    message = await first_text(client, alex, dm, None)

    response = await client.put(f"/api/v1/messages/{message['id']}/reaction", headers=alex, json=body)

    assert response.status_code == 422


async def test_reaction_permissions(client: AsyncClient, alex: dict[str, str]) -> None:
    trip = await chat_id(client, alex, "Weekend Trip")
    early = await first_text(client, alex, trip, None)  # before Emma joined, before Daniel left

    assert await react(client, await login(client, EMMA), early["id"], "❤️") == 404  # can't see it
    assert await react(client, await login(client, DANIEL), early["id"], "❤️") == 403  # removed: read-only
    assert await react(client, alex, 999999, "❤️") == 404


async def test_blocks_hide_reactions_and_stop_reacting_in_the_dm(client: AsyncClient, alex: dict[str, str]) -> None:
    dm = await chat_id(client, alex, "Priya Sharma")
    message = await first_text(client, alex, dm, None)
    priya = await login(client, PRIYA)
    priya_id = (await client.get("/api/v1/users/me", headers=priya)).json()["id"]
    assert await react(client, priya, message["id"], "❤️") == 204

    await client.put(f"/api/v1/blocks/{priya_id}", headers=alex)

    assert (await find(client, alex, dm, message["id"]))["reactions"] == []
    assert await react(client, alex, message["id"], "👍") == 403
    await client.delete(f"/api/v1/blocks/{priya_id}", headers=alex)
    assert [r["emoji"] for r in (await find(client, alex, dm, message["id"]))["reactions"]] == ["❤️"]
