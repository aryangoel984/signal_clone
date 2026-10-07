"""Shared helpers for API tests that run against the seeded demo data."""

from typing import Any

from httpx import AsyncClient

from tests.conftest import bearer, sign_in

ALEX = "+15550100001"
PRIYA = "+15550100002"
MARCUS = "+15550100003"
SOFIA = "+15550100004"
DANIEL = "+15550100005"
EMMA = "+15550100006"
LENA = "+15550100008"


async def login(client: AsyncClient, phone: str) -> dict[str, str]:
    token, _ = await sign_in(client, phone)
    return bearer(token)


async def chat_id(client: AsyncClient, headers: dict[str, str], title: str) -> int:
    chats = (await client.get("/api/v1/conversations", headers=headers)).json()
    return next(chat["id"] for chat in chats if chat["title"] == title)


async def chat(client: AsyncClient, headers: dict[str, str], title: str) -> dict[str, Any]:
    chats = (await client.get("/api/v1/conversations", headers=headers)).json()
    return next(chat for chat in chats if chat["title"] == title)


async def messages(client: AsyncClient, headers: dict[str, str], conversation_id: int, **params: int) -> dict[str, Any]:
    response = await client.get(f"/api/v1/conversations/{conversation_id}/messages", headers=headers, params=params)
    assert response.status_code == 200, response.text
    return response.json()


async def send(client: AsyncClient, headers: dict[str, str], conversation_id: int, body: str, client_id: str):  # noqa: ANN201
    return await client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        headers=headers,
        json={"client_id": client_id, "body": body},
    )
