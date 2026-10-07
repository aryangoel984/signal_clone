import pytest
from httpx import AsyncClient

from app.core.db import Database
from app.seed import run_seed
from app.seed_data import DEMO_PHONE
from tests.conftest import bearer, sign_in

HIRO_PHONE = "+15550100007"


@pytest.fixture
async def alex(client: AsyncClient, database: Database) -> dict[str, str]:
    await run_seed(database)
    token, _ = await sign_in(client, DEMO_PHONE)
    return bearer(token)


async def user_id_by_phone(client: AsyncClient, headers: dict[str, str], phone: str) -> int:
    return (await client.get("/api/v1/users/search", headers=headers, params={"q": phone})).json()[0]["id"]


async def test_lists_contacts_alphabetically(client: AsyncClient, alex: dict[str, str]) -> None:
    names = [contact["name"] for contact in (await client.get("/api/v1/contacts", headers=alex)).json()]

    assert names == sorted(names, key=str.casefold)
    assert "Priya Sharma" in names and "Hiro Tanaka" not in names


async def test_add_contact_by_phone(client: AsyncClient, alex: dict[str, str]) -> None:
    response = await client.post("/api/v1/contacts", headers=alex, json={"phone_number": "+1 555 010 0007"})

    assert response.status_code == 201
    assert response.json()["name"] == "Hiro Tanaka"
    assert response.json()["phone_number"] == HIRO_PHONE  # visible now that he's a contact


async def test_add_contact_by_username(client: AsyncClient, alex: dict[str, str]) -> None:
    stranger, _ = await sign_in(client, "+15557770009")
    await client.patch("/api/v1/users/me", headers=bearer(stranger), json={"display_name": "Zoe", "username": "zoe.42"})

    response = await client.post("/api/v1/contacts", headers=alex, json={"username": "Zoe.42"})

    assert response.status_code == 201
    assert response.json()["name"] == "Zoe"


@pytest.mark.parametrize(
    ("body", "status"),
    [
        ({"phone_number": "+15550100002"}, 409),  # Priya: already a contact
        ({"phone_number": "+15559999999"}, 404),  # nobody
        ({"phone_number": DEMO_PHONE}, 400),  # myself
        ({"phone_number": HIRO_PHONE, "username": "x.12"}, 422),  # two identifiers
        ({}, 422),  # none
    ],
)
async def test_add_contact_errors(client: AsyncClient, alex: dict[str, str], body: dict[str, str], status: int) -> None:
    response = await client.post("/api/v1/contacts", headers=alex, json=body)

    assert response.status_code == status


async def test_nickname_renames_the_dm(client: AsyncClient, alex: dict[str, str]) -> None:
    sofia_id = await user_id_by_phone(client, alex, "+15550100004")

    response = await client.patch(f"/api/v1/contacts/{sofia_id}", headers=alex, json={"nickname": "Sof"})
    titles = [chat["title"] for chat in (await client.get("/api/v1/conversations", headers=alex)).json()]

    assert response.json()["name"] == "Sof"
    assert "Sof" in titles and "Sofia Rossi" not in titles


async def test_remove_contact(client: AsyncClient, alex: dict[str, str]) -> None:
    priya_id = await user_id_by_phone(client, alex, "+15550100002")

    assert (await client.delete(f"/api/v1/contacts/{priya_id}", headers=alex)).status_code == 204
    assert (await client.delete(f"/api/v1/contacts/{priya_id}", headers=alex)).status_code == 404


async def test_public_profile_hides_phone_of_non_contacts(client: AsyncClient, alex: dict[str, str]) -> None:
    hiro_id = await user_id_by_phone(client, alex, HIRO_PHONE)
    priya_id = await user_id_by_phone(client, alex, "+15550100002")

    hiro = (await client.get(f"/api/v1/users/{hiro_id}", headers=alex)).json()
    priya = (await client.get(f"/api/v1/users/{priya_id}", headers=alex)).json()

    assert hiro["phone_number"] is None and hiro["is_contact"] is False
    assert priya["phone_number"] == "+15550100002" and priya["is_contact"] is True
    assert (await client.get("/api/v1/users/99999", headers=alex)).status_code == 404
