import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import Database
from app.models import ConversationMember, MessageReceipt
from app.seed import run_seed
from tests.helpers import ALEX, DANIEL, EMMA, chat_id, login, messages, send


@pytest.fixture
async def alex(client: AsyncClient, database: Database) -> dict[str, str]:
    await run_seed(database)
    return await login(client, ALEX)


# --- history -------------------------------------------------------------------------------


async def test_pages_through_history_without_gaps(client: AsyncClient, alex: dict[str, str]) -> None:
    priya = await chat_id(client, alex, "Priya Sharma")

    first = await messages(client, alex, priya)
    second = await messages(client, alex, priya, before=first["next_cursor"])

    assert len(first["items"]) == 50 and len(second["items"]) == 6
    assert second["next_cursor"] is None
    ids = [m["id"] for m in second["items"] + first["items"]]
    assert ids == sorted(ids) and len(set(ids)) == 56  # oldest first, no gaps or duplicates
    assert first["next_cursor"] == first["items"][0]["id"]


async def test_after_returns_newer_messages(client: AsyncClient, alex: dict[str, str]) -> None:
    priya = await chat_id(client, alex, "Priya Sharma")
    page = await messages(client, alex, priya)

    newer = await messages(client, alex, priya, after=page["items"][-3]["id"])

    assert [m["id"] for m in newer["items"]] == [m["id"] for m in page["items"][-2:]]


async def test_history_is_viewer_relative(client: AsyncClient, alex: dict[str, str]) -> None:
    trip = await chat_id(client, alex, "Weekend Trip")

    items = (await messages(client, alex, trip))["items"]

    assert items[0]["text"] == "You created the group."
    mine = [m for m in items if m["sender_name"] is None and m["kind"] == "text"]
    theirs = [m for m in items if m["sender_name"] is not None]
    assert all(m["status"] is not None and m["client_id"] for m in mine)
    assert all(m["status"] is None and m["client_id"] is None for m in theirs)
    assert {m["sender_name"] for m in theirs} >= {"Priya Sharma", "Marcus Chen"}
    assert all(m["sender_avatar_color"] for m in items)


async def test_added_member_history_starts_at_being_added(client: AsyncClient, database: Database) -> None:
    await run_seed(database)
    emma = await login(client, EMMA)
    trip = await chat_id(client, emma, "Weekend Trip")

    items = (await messages(client, emma, trip))["items"]

    assert items[0]["text"] == "Alex Rivera added you."


async def test_removed_member_history_ends_at_removal(client: AsyncClient, database: Database) -> None:
    await run_seed(database)
    daniel = await login(client, DANIEL)
    trip = await chat_id(client, daniel, "Weekend Trip")

    items = (await messages(client, daniel, trip))["items"]

    assert items[-1]["text"] == "Alex Rivera removed you."


async def test_history_of_unknown_conversation_is_404(client: AsyncClient, alex: dict[str, str]) -> None:
    response = await client.get("/api/v1/conversations/99999/messages", headers=alex)

    assert response.status_code == 404


@pytest.mark.parametrize("limit", [0, 101])
async def test_limit_is_bounded(client: AsyncClient, alex: dict[str, str], limit: int) -> None:
    response = await client.get(f"/api/v1/conversations/{await chat_id(client, alex, 'Marcus Chen')}/messages", headers=alex, params={"limit": limit})

    assert response.status_code == 422


# --- send -------------------------------------------------------------------------------------


async def test_send_creates_message_and_receipts(client: AsyncClient, alex: dict[str, str], session: AsyncSession) -> None:
    trip = await chat_id(client, alex, "Weekend Trip")

    response = await send(client, alex, trip, "  Who's bringing the speaker?  ", "c-0000-0001")

    assert response.status_code == 201
    message = response.json()
    assert message["text"] == "Who's bringing the speaker?"  # trimmed
    assert message["status"] == "sent" and message["sender_name"] is None
    receipts = await session.scalar(
        select(func.count()).select_from(MessageReceipt).where(MessageReceipt.message_id == message["id"])
    )
    assert receipts == 4  # Priya, Marcus, Sofia, Emma - not Alex, not removed Daniel
    chats = (await client.get("/api/v1/conversations", headers=alex)).json()
    assert chats[0]["id"] == trip and chats[0]["last_message"]["id"] == message["id"]


async def test_send_moves_senders_watermark(client: AsyncClient, alex: dict[str, str], session: AsyncSession) -> None:
    book_club = await chat_id(client, alex, "Book Club")

    message = (await send(client, alex, book_club, "Catching up now", "c-0000-0002")).json()

    watermark = await session.scalar(
        select(ConversationMember.last_read_message_id).where(
            ConversationMember.conversation_id == book_club, ConversationMember.user_id == message["sender_id"]
        )
    )
    assert watermark == message["id"]


async def test_retry_with_same_client_id_is_idempotent(client: AsyncClient, alex: dict[str, str], session: AsyncSession) -> None:
    marcus = await chat_id(client, alex, "Marcus Chen")

    first = await send(client, alex, marcus, "See you at 8", "c-0000-0003")
    retry = await send(client, alex, marcus, "See you at 8", "c-0000-0003")

    assert first.status_code == 201 and retry.status_code == 200
    assert retry.json()["id"] == first.json()["id"]
    receipts = await session.scalar(
        select(func.count()).select_from(MessageReceipt).where(MessageReceipt.message_id == first.json()["id"])
    )
    assert receipts == 1


async def test_client_id_reused_in_other_conversation_is_409(client: AsyncClient, alex: dict[str, str]) -> None:
    await send(client, alex, await chat_id(client, alex, "Marcus Chen"), "hi", "c-0000-0004")

    response = await send(client, alex, await chat_id(client, alex, "Sofia Rossi"), "hi", "c-0000-0004")

    assert response.status_code == 409


async def test_removed_member_cannot_send(client: AsyncClient, database: Database) -> None:
    await run_seed(database)
    daniel = await login(client, DANIEL)

    response = await send(client, daniel, await chat_id(client, daniel, "Weekend Trip"), "hello?", "c-0000-0005")

    assert response.status_code == 403


@pytest.mark.parametrize(
    "body",
    [
        {"client_id": "c-0000-0006", "body": ""},
        {"client_id": "c-0000-0006", "body": " \n\t "},
        {"client_id": "c-0000-0006", "body": "x" * 4001},
        {"client_id": "bad", "body": "hi"},
        {"body": "hi"},
    ],
)
async def test_invalid_send_is_422(client: AsyncClient, alex: dict[str, str], body: dict[str, str]) -> None:
    marcus = await chat_id(client, alex, "Marcus Chen")

    response = await client.post(f"/api/v1/conversations/{marcus}/messages", headers=alex, json=body)

    assert response.status_code == 422


async def test_multiline_body_keeps_inner_newlines(client: AsyncClient, alex: dict[str, str]) -> None:
    marcus = await chat_id(client, alex, "Marcus Chen")

    response = await send(client, alex, marcus, "line one\nline two\n", "c-0000-0007")

    assert response.json()["text"] == "line one\nline two"


async def test_send_requires_auth(client: AsyncClient, database: Database) -> None:
    response = await client.post("/api/v1/conversations/1/messages", json={"client_id": "c-0000-0008", "body": "hi"})

    assert response.status_code == 401
