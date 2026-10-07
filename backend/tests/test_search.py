import pytest
from httpx import AsyncClient

from app.core.db import Database
from app.seed import run_seed
from app.seed_data import DEMO_PHONE
from tests.conftest import bearer, sign_in


@pytest.fixture
async def alex(client: AsyncClient, database: Database) -> dict[str, str]:
    await run_seed(database)
    token, _ = await sign_in(client, DEMO_PHONE)
    return bearer(token)


async def search(client: AsyncClient, headers: dict[str, str], q: str) -> list[str]:
    response = await client.get("/api/v1/users/search", headers=headers, params={"q": q})
    assert response.status_code == 200, response.text
    return [user["name"] for user in response.json()]


async def test_exact_phone_finds_anyone(client: AsyncClient, alex: dict[str, str]) -> None:
    assert await search(client, alex, "+1 (555) 010-0007") == ["Hiro Tanaka"]  # not a contact


async def test_partial_phone_finds_nobody(client: AsyncClient, alex: dict[str, str]) -> None:
    assert await search(client, alex, "+155501000") == []


async def test_username_prefix_finds_anyone(client: AsyncClient, alex: dict[str, str]) -> None:
    stranger, _ = await sign_in(client, "+15557770009")
    await client.patch("/api/v1/users/me", headers=bearer(stranger), json={"display_name": "Zoe", "username": "zoe.42"})

    assert await search(client, alex, "@zo") == ["Zoe"]
    assert await search(client, alex, "pri") == ["Priya Sharma"]


async def test_name_search_only_covers_contacts(client: AsyncClient, alex: dict[str, str]) -> None:
    assert await search(client, alex, "sofia") == ["Sofia Rossi"]
    assert await search(client, alex, "hiro") == []  # Hiro exists but isn't Alex's contact


async def test_never_returns_yourself(client: AsyncClient, alex: dict[str, str]) -> None:
    assert "Alex Rivera" not in await search(client, alex, "alex")
    assert await search(client, alex, DEMO_PHONE) == []


async def test_users_without_profile_are_hidden(client: AsyncClient, alex: dict[str, str]) -> None:
    await sign_in(client, "+15557770010")  # registered, never finished onboarding

    assert await search(client, alex, "+15557770010") == []


@pytest.mark.parametrize("q", ["", "   ", "%", "_", "a%b"])
async def test_empty_and_wildcard_queries_match_nothing_unexpected(
    client: AsyncClient, alex: dict[str, str], q: str
) -> None:
    assert await search(client, alex, q) == []
