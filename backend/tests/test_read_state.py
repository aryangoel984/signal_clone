import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import Database
from app.models import Message, MessageReceipt
from app.seed import run_seed
from tests.helpers import ALEX, EMMA, LENA, chat, chat_id, login, messages


@pytest.fixture
async def alex(client: AsyncClient, database: Database) -> dict[str, str]:
    await run_seed(database)
    return await login(client, ALEX)


async def read(client: AsyncClient, headers: dict[str, str], conversation_id: int, up_to: int) -> None:
    response = await client.post(
        f"/api/v1/conversations/{conversation_id}/read", headers=headers, json={"up_to_message_id": up_to}
    )
    assert response.status_code == 204, response.text


async def watermark(client: AsyncClient, headers: dict[str, str], conversation_id: int) -> int:
    return (await client.get(f"/api/v1/conversations/{conversation_id}", headers=headers)).json()["last_read_message_id"]


async def test_reading_clears_unread_and_sets_read_at(client: AsyncClient, alex: dict[str, str], session: AsyncSession) -> None:
    sofia = await chat_id(client, alex, "Sofia Rossi")
    newest = (await messages(client, alex, sofia))["items"][-1]["id"]

    await read(client, alex, sofia, newest)

    assert (await chat(client, alex, "Sofia Rossi"))["unread_count"] == 0
    assert await watermark(client, alex, sofia) == newest
    unread = (
        await session.execute(
            select(MessageReceipt)
            .join(Message, Message.id == MessageReceipt.message_id)
            .where(Message.conversation_id == sofia, MessageReceipt.read_at.is_(None), MessageReceipt.user_id != Message.sender_id)
        )
    ).scalars().all()
    assert [r for r in unread if r.user_id == (await client.get("/api/v1/users/me", headers=alex)).json()["id"]] == []


async def test_partial_read_leaves_rest_unread(client: AsyncClient, alex: dict[str, str]) -> None:
    book_club = await chat_id(client, alex, "Book Club")
    items = (await messages(client, alex, book_club))["items"]

    await read(client, alex, book_club, items[-3]["id"])

    assert (await chat(client, alex, "Book Club"))["unread_count"] == 2


async def test_watermark_never_moves_backward(client: AsyncClient, alex: dict[str, str]) -> None:
    sofia = await chat_id(client, alex, "Sofia Rossi")
    items = (await messages(client, alex, sofia))["items"]
    await read(client, alex, sofia, items[-1]["id"])

    await read(client, alex, sofia, items[0]["id"])

    assert await watermark(client, alex, sofia) == items[-1]["id"]


async def test_watermark_is_clamped_to_newest_visible(client: AsyncClient, alex: dict[str, str]) -> None:
    sofia = await chat_id(client, alex, "Sofia Rossi")
    newest = (await messages(client, alex, sofia))["items"][-1]["id"]

    await read(client, alex, sofia, 10_000_000)

    assert await watermark(client, alex, sofia) == newest


async def test_receipts_off_moves_watermark_but_records_no_read(client: AsyncClient, alex: dict[str, str], session: AsyncSession) -> None:
    lena = await login(client, LENA)
    dm = await chat_id(client, lena, "Alex Rivera")
    await client.post(
        f"/api/v1/conversations/{dm}/messages", headers=alex, json={"client_id": "c-read-0001", "body": "new one"}
    )
    newest = (await messages(client, lena, dm))["items"][-1]["id"]

    await read(client, lena, dm, newest)

    assert await watermark(client, lena, dm) == newest
    receipt = (await session.execute(select(MessageReceipt).where(MessageReceipt.message_id == newest))).scalar_one()
    assert receipt.read_at is None
    assert receipt.delivered_at is not None  # she loaded her chat list, so it was delivered
    assert (await chat(client, alex, "Lena Fischer"))["last_message"]["status"] == "delivered"


async def test_read_of_unknown_conversation_is_404(client: AsyncClient, alex: dict[str, str]) -> None:
    response = await client.post("/api/v1/conversations/99999/read", headers=alex, json={"up_to_message_id": 1})

    assert response.status_code == 404


async def test_loading_chat_list_marks_pending_messages_delivered(client: AsyncClient, alex: dict[str, str]) -> None:
    assert (await chat(client, alex, "Emma Larsen"))["last_message"]["status"] == "sent"

    emma = await login(client, EMMA)
    await client.get("/api/v1/conversations", headers=emma)

    assert (await chat(client, alex, "Emma Larsen"))["last_message"]["status"] == "delivered"


async def test_read_by_recipient_shows_as_read_to_sender(client: AsyncClient, alex: dict[str, str]) -> None:
    emma = await login(client, EMMA)
    dm = await chat_id(client, emma, "Alex Rivera")
    newest = (await messages(client, emma, dm))["items"][-1]["id"]

    await read(client, emma, dm, newest)

    assert (await chat(client, alex, "Emma Larsen"))["last_message"]["status"] == "read"
