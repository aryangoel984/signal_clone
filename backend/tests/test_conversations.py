from typing import Any

import pytest
from httpx import AsyncClient

from app.core.db import Database
from app.seed import run_seed
from app.seed_data import DEMO_PHONE, SECOND_DEMO_PHONE
from tests.conftest import bearer, sign_in

DANIEL_PHONE = "+15550100005"
HIRO_PHONE = "+15550100007"


@pytest.fixture
async def alex(client: AsyncClient, database: Database) -> dict[str, str]:
    await run_seed(database)
    token, _ = await sign_in(client, DEMO_PHONE)
    return bearer(token)


async def chat_list(client: AsyncClient, headers: dict[str, str], archived: bool = False) -> list[dict[str, Any]]:
    response = await client.get("/api/v1/conversations", headers=headers, params={"archived": archived})
    assert response.status_code == 200, response.text
    return response.json()


def by_title(chats: list[dict[str, Any]], title: str) -> dict[str, Any]:
    return next(chat for chat in chats if chat["title"] == title)


# --- chat list ---------------------------------------------------------------------------


async def test_list_is_ordered_by_last_visible_message(client: AsyncClient, alex: dict[str, str]) -> None:
    titles = [chat["title"] for chat in await chat_list(client, alex)]

    # Seed timings (minutes ago of the last message): Sofia 8, Book Club 15, Emma 25, Daniel 40,
    # Weekend Trip 60, Marcus 95, Lena 304, Maya 596, Leo 646, Recipe Swap 689, Priya 760, spammer 2990.
    assert titles == [
        "Sofia Rossi",
        "Book Club",
        "Emma Larsen",
        "Daniel Okafor",
        "Weekend Trip",
        "Marcus Chen",
        "Lena Fischer",
        "Maya (bot)",
        "Leo (bot)",
        "Recipe Swap",
        "Priya Sharma",
        "Crypto Deals",
    ]


async def test_unread_counts_and_incoming_preview(client: AsyncClient, alex: dict[str, str]) -> None:
    chats = await chat_list(client, alex)
    sofia = by_title(chats, "Sofia Rossi")

    assert {chat["title"]: chat["unread_count"] for chat in chats if chat["unread_count"]} == {
        "Sofia Rossi": 3,
        "Book Club": 5,
    }
    assert sofia["last_message"]["text"] == "Also bring your camera, the market is on 📷"
    assert sofia["last_message"]["sender_name"] == "Sofia Rossi"
    assert sofia["last_message"]["status"] is None  # not my message


@pytest.mark.parametrize(
    ("title", "status"),
    [
        ("Emma Larsen", "sent"),
        ("Daniel Okafor", "delivered"),
        ("Lena Fischer", "delivered"),  # Lena has read receipts off
        ("Weekend Trip", "delivered"),  # Marcus hasn't read it
        ("Marcus Chen", "read"),
    ],
)
async def test_status_of_my_last_message(client: AsyncClient, alex: dict[str, str], title: str, status: str) -> None:
    last = by_title(await chat_list(client, alex), title)["last_message"]

    assert last["sender_id"] is not None and last["sender_name"] is None  # mine
    assert last["status"] == status


async def test_dm_rows_expose_the_other_person(client: AsyncClient, alex: dict[str, str]) -> None:
    chats = await chat_list(client, alex)

    assert by_title(chats, "Marcus Chen")["is_contact"] is True
    assert by_title(chats, "Crypto Deals")["is_contact"] is False
    assert by_title(chats, "Weekend Trip")["other_user_id"] is None


async def test_removed_member_sees_list_bounded_by_history(client: AsyncClient, database: Database) -> None:
    await run_seed(database)
    token, _ = await sign_in(client, DANIEL_PHONE)

    chats = await chat_list(client, bearer(token))
    trip = by_title(chats, "Weekend Trip")

    assert trip["last_message"]["text"] == "Alex Rivera removed you."
    assert trip["unread_count"] == 0
    assert trip["is_active"] is False
    assert [chat["title"] for chat in chats] == ["Alex Rivera", "Weekend Trip"]  # trip sorts by his removal


async def test_empty_dm_is_hidden_but_openable(client: AsyncClient, alex: dict[str, str]) -> None:
    hiro_id = (await client.get("/api/v1/users/search", headers=alex, params={"q": HIRO_PHONE})).json()[0]["id"]

    created = await client.post("/api/v1/conversations/direct", headers=alex, json={"user_id": hiro_id})

    assert created.status_code == 201
    assert created.json()["last_message"] is None
    assert "Hiro Tanaka" not in [chat["title"] for chat in await chat_list(client, alex)]
    detail = await client.get(f"/api/v1/conversations/{created.json()['id']}", headers=alex)
    assert detail.status_code == 200


# --- get-or-create DM ------------------------------------------------------------------


async def test_get_or_create_dm_returns_existing(client: AsyncClient, alex: dict[str, str]) -> None:
    marcus = by_title(await chat_list(client, alex), "Marcus Chen")

    response = await client.post("/api/v1/conversations/direct", headers=alex, json={"user_id": marcus["other_user_id"]})

    assert response.status_code == 200
    assert response.json()["id"] == marcus["id"]


async def test_cannot_dm_yourself(client: AsyncClient, alex: dict[str, str]) -> None:
    me = (await client.get("/api/v1/users/me", headers=alex)).json()

    response = await client.post("/api/v1/conversations/direct", headers=alex, json={"user_id": me["id"]})

    assert response.status_code == 400


async def test_cannot_dm_unknown_user(client: AsyncClient, alex: dict[str, str]) -> None:
    response = await client.post("/api/v1/conversations/direct", headers=alex, json={"user_id": 99999})

    assert response.status_code == 404


# --- detail and access ----------------------------------------------------------------


async def test_group_detail_lists_active_members(client: AsyncClient, alex: dict[str, str]) -> None:
    trip_id = by_title(await chat_list(client, alex), "Weekend Trip")["id"]

    detail = (await client.get(f"/api/v1/conversations/{trip_id}", headers=alex)).json()

    names = [member["name"] for member in detail["members"]]
    assert "Daniel Okafor" not in names  # removed
    assert {"You", "Priya Sharma", "Marcus Chen", "Sofia Rossi", "Emma Larsen"} == set(names)
    assert detail["my_role"] == "admin"
    assert detail["member_count"] == 5


@pytest.mark.parametrize(
    ("title", "groups"),
    [
        ("Priya Sharma", ["Book Club", "Weekend Trip"]),
        ("Daniel Okafor", []),  # removed from Weekend Trip, so no longer in common
        ("Maya (bot)", ["Recipe Swap"]),
    ],
)
async def test_dm_detail_lists_groups_in_common(
    client: AsyncClient, alex: dict[str, str], title: str, groups: list[str]
) -> None:
    chat_id = by_title(await chat_list(client, alex), title)["id"]

    detail = (await client.get(f"/api/v1/conversations/{chat_id}", headers=alex)).json()

    assert detail["groups_in_common"] == groups


async def test_non_member_gets_404(client: AsyncClient, alex: dict[str, str]) -> None:
    priya_token, _ = await sign_in(client, SECOND_DEMO_PHONE)
    priya_marcus = by_title(await chat_list(client, bearer(priya_token)), "Marcus Chen")["id"]

    response = await client.get(f"/api/v1/conversations/{priya_marcus}", headers=alex)

    assert response.status_code == 404


async def test_list_requires_auth(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/conversations")).status_code == 401


# --- preferences ---------------------------------------------------------------------------


async def test_pinning_moves_chat_to_top(client: AsyncClient, alex: dict[str, str]) -> None:
    recipe = by_title(await chat_list(client, alex), "Recipe Swap")

    response = await client.patch(
        f"/api/v1/conversations/{recipe['id']}/preferences", headers=alex, json={"is_pinned": True}
    )

    assert response.json()["is_pinned"] is True
    assert (await chat_list(client, alex))[0]["title"] == "Recipe Swap"


async def test_archiving_moves_chat_to_archive(client: AsyncClient, alex: dict[str, str]) -> None:
    lena = by_title(await chat_list(client, alex), "Lena Fischer")

    await client.patch(f"/api/v1/conversations/{lena['id']}/preferences", headers=alex, json={"is_archived": True})

    assert "Lena Fischer" not in [chat["title"] for chat in await chat_list(client, alex)]
    assert [chat["title"] for chat in await chat_list(client, alex, archived=True)] == ["Lena Fischer"]


async def test_preferences_reject_unknown_fields(client: AsyncClient, alex: dict[str, str]) -> None:
    chat_id = (await chat_list(client, alex))[0]["id"]

    response = await client.patch(f"/api/v1/conversations/{chat_id}/preferences", headers=alex, json={"role": "admin"})

    assert response.status_code == 422
