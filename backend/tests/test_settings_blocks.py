from typing import Any

import pytest
from httpx import AsyncClient

from app.core.db import Database
from app.seed import run_seed
from tests.helpers import ALEX, LENA, PRIYA, SOFIA, chat, chat_id, login, messages, send

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


@pytest.fixture
async def alex(client: AsyncClient, database: Database) -> dict[str, str]:
    await run_seed(database)
    return await login(client, ALEX)


async def user_id(client: AsyncClient, headers: dict[str, str]) -> int:
    return (await client.get("/api/v1/users/me", headers=headers)).json()["id"]


async def patch_settings(client: AsyncClient, headers: dict[str, str], **changes: Any) -> Any:
    return await client.patch("/api/v1/users/me/settings", headers=headers, json=changes)


# --- settings ----------------------------------------------------------------------------------------


async def test_settings_defaults_and_patch(client: AsyncClient, alex: dict[str, str]) -> None:
    defaults = (await client.get("/api/v1/users/me/settings", headers=alex)).json()
    assert defaults == {
        "theme": "system",
        "read_receipts_enabled": True,
        "typing_indicators_enabled": True,
        "notifications_enabled": True,
        "enter_key_sends": True,
    }

    updated = (await patch_settings(client, alex, theme="dark", enter_key_sends=False)).json()

    assert updated["theme"] == "dark" and updated["enter_key_sends"] is False
    assert updated["read_receipts_enabled"] is True  # untouched


@pytest.mark.parametrize("body", [{"theme": "blue"}, {"unknown": True}, {"read_receipts_enabled": "maybe"}])
async def test_invalid_settings_are_rejected(client: AsyncClient, alex: dict[str, str], body: dict[str, Any]) -> None:
    assert (await client.patch("/api/v1/users/me/settings", headers=alex, json=body)).status_code == 422


async def test_read_receipts_off_stops_sending_reads(client: AsyncClient, alex: dict[str, str]) -> None:
    sofia = await login(client, SOFIA)
    dm = await chat_id(client, alex, "Sofia Rossi")
    await patch_settings(client, alex, read_receipts_enabled=False)

    newest = (await messages(client, alex, dm))["items"][-1]["id"]
    await client.post(f"/api/v1/conversations/{dm}/read", headers=alex, json={"up_to_message_id": newest})

    assert (await chat(client, alex, "Sofia Rossi"))["unread_count"] == 0  # Alex's own badge still clears
    assert (await chat(client, sofia, "Alex Rivera"))["last_message"]["status"] == "delivered"  # never "read"


# --- blocks ---------------------------------------------------------------------------------------------


async def test_block_list_and_validation(client: AsyncClient, alex: dict[str, str]) -> None:
    priya_id = await user_id(client, await login(client, PRIYA))

    assert (await client.put(f"/api/v1/blocks/{priya_id}", headers=alex)).status_code == 204
    assert (await client.put(f"/api/v1/blocks/{priya_id}", headers=alex)).status_code == 204  # idempotent
    names = [u["name"] for u in (await client.get("/api/v1/blocks", headers=alex)).json()]
    assert "Priya Sharma" in names and "Crypto Deals" in names  # the seeded block too
    assert (await client.put(f"/api/v1/blocks/{await user_id(client, alex)}", headers=alex)).status_code == 400
    assert (await client.put("/api/v1/blocks/99999", headers=alex)).status_code == 404
    assert (await client.delete(f"/api/v1/blocks/{priya_id}", headers=alex)).status_code == 204
    assert "Priya Sharma" not in [u["name"] for u in (await client.get("/api/v1/blocks", headers=alex)).json()]


async def test_blocker_must_unblock_to_send(client: AsyncClient, alex: dict[str, str]) -> None:
    priya = await login(client, PRIYA)
    dm = await chat_id(client, alex, "Priya Sharma")
    await client.put(f"/api/v1/blocks/{await user_id(client, priya)}", headers=alex)

    blocked = await send(client, alex, dm, "hi", "c-blk-0001")

    assert blocked.status_code == 403
    assert blocked.json()["detail"] == "Unblock this person to send messages"
    await client.delete(f"/api/v1/blocks/{await user_id(client, priya)}", headers=alex)
    assert (await send(client, alex, dm, "hi", "c-blk-0002")).status_code == 201


async def test_blocked_sender_gets_normal_success_but_nothing_is_delivered(client: AsyncClient, alex: dict[str, str]) -> None:
    priya = await login(client, PRIYA)
    await client.put(f"/api/v1/blocks/{await user_id(client, priya)}", headers=alex)
    dm = await chat_id(client, priya, "Alex Rivera")

    response = await send(client, priya, dm, "Are you there?", "c-blk-0003")

    assert response.status_code == 201  # no error: Signal doesn't reveal blocks
    assert response.json()["status"] == "sent"
    await client.get("/api/v1/conversations", headers=alex)  # Alex's client "connects": delivers pending
    mine = next(m for m in (await messages(client, priya, dm))["items"] if m["text"] == "Are you there?")
    assert mine["status"] == "sent"  # one tick forever: no delivered/read
    details = (await client.get(f"/api/v1/messages/{mine['id']}/receipts", headers=priya)).json()
    assert details["recipients"] == []
    assert "Are you there?" not in [m["text"] for m in (await messages(client, alex, dm))["items"]]


async def test_blocked_users_group_name_and_photo_are_hidden(client: AsyncClient, alex: dict[str, str]) -> None:
    priya = await login(client, PRIYA)  # admin of Book Club
    lena = await login(client, LENA)
    book_club = await chat_id(client, alex, "Book Club")
    await client.put(f"/api/v1/blocks/{await user_id(client, priya)}", headers=alex)

    await client.patch(f"/api/v1/groups/{book_club}", headers=priya, json={"name": "Priya's Club"})
    await client.put(f"/api/v1/groups/{book_club}/avatar", headers=priya, files={"file": ("g.png", PNG, "image/png")})

    for_alex = (await client.get(f"/api/v1/conversations/{book_club}", headers=alex)).json()
    for_lena = (await client.get(f"/api/v1/conversations/{book_club}", headers=lena)).json()
    assert (for_alex["title"], for_alex["avatar_url"]) == ("Book Club", None)
    assert any(c["title"] == "Book Club" for c in (await client.get("/api/v1/conversations", headers=alex)).json())
    assert for_lena["title"] == "Priya's Club" and for_lena["avatar_url"].startswith("/media/groups/")
