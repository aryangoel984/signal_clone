from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import Database
from app.core.security import hash_session_token
from app.core.time import utc_now
from app.models import User, UserSession, UserSettings
from app.seed import run_seed
from app.seed_data import DEMO_PHONE
from tests.conftest import bearer, sign_in

# --- OTP request --------------------------------------------------------------------


async def test_otp_request_accepts_valid_number(client: AsyncClient) -> None:
    response = await client.post("/api/v1/auth/otp/request", json={"phone_number": "+14155550123"})

    assert response.status_code == 202
    assert response.json() == {"sent": True}


async def test_otp_request_normalizes_separators(client: AsyncClient, session: AsyncSession) -> None:
    await client.post("/api/v1/auth/otp/request", json={"phone_number": "+1 (415) 555-0123"})
    token, body = await sign_in(client, "+1 415-555-0123")

    assert body["user"]["phone_number"] == "+14155550123"
    assert token


@pytest.mark.parametrize("phone", ["12345", "4155550123", "+0415555012", "+1415abc0123", "+1234567", ""])
async def test_otp_request_rejects_non_e164(client: AsyncClient, phone: str) -> None:
    response = await client.post("/api/v1/auth/otp/request", json={"phone_number": phone})

    assert response.status_code == 422


# --- OTP verify -----------------------------------------------------------------------


async def test_wrong_code_is_rejected(client: AsyncClient) -> None:
    response = await client.post("/api/v1/auth/otp/verify", json={"phone_number": "+14155550123", "code": "000000"})

    assert response.status_code == 400
    assert response.json() == {"detail": "Incorrect verification code"}


async def test_unknown_number_registers_new_user(client: AsyncClient, session: AsyncSession) -> None:
    _, body = await sign_in(client, "+14155550123")

    assert body["is_new_user"] is True
    assert body["user"]["display_name"] is None
    user = (await session.execute(select(User).where(User.phone_number == "+14155550123"))).scalar_one()
    assert await session.get(UserSettings, user.id) is not None


async def test_known_number_logs_in_without_duplicating(
    client: AsyncClient, database: Database, session: AsyncSession
) -> None:
    await run_seed(database)
    users_before = await session.scalar(select(func.count()).select_from(User))

    _, body = await sign_in(client, DEMO_PHONE)

    assert body["is_new_user"] is False
    assert body["user"]["display_name"] == "Alex Rivera"
    assert await session.scalar(select(func.count()).select_from(User)) == users_before


async def test_token_is_stored_hashed_with_30_day_expiry(client: AsyncClient, session: AsyncSession) -> None:
    token, _ = await sign_in(client)

    stored = (await session.execute(select(UserSession))).scalar_one()
    assert stored.token_hash == hash_session_token(token)
    assert stored.token_hash != token
    assert timedelta(days=29, hours=23) < stored.expires_at - utc_now() <= timedelta(days=30)


# --- get_current_user --------------------------------------------------------------


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer not-a-real-token"}, {"Authorization": "Basic abc"}])
async def test_me_requires_valid_bearer_token(client: AsyncClient, headers: dict[str, str]) -> None:
    response = await client.get("/api/v1/users/me", headers=headers)

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


async def test_expired_session_is_rejected(client: AsyncClient, session: AsyncSession) -> None:
    token, _ = await sign_in(client)
    await session.execute(update(UserSession).values(expires_at=utc_now() - timedelta(seconds=1)))
    await session.commit()

    response = await client.get("/api/v1/users/me", headers=bearer(token))

    assert response.status_code == 401


async def test_valid_token_returns_profile(client: AsyncClient) -> None:
    token, _ = await sign_in(client, "+14155550123")

    response = await client.get("/api/v1/users/me", headers=bearer(token))

    assert response.status_code == 200
    assert response.json()["phone_number"] == "+14155550123"


# --- logout -------------------------------------------------------------------------


async def test_logout_revokes_only_that_session(client: AsyncClient) -> None:
    laptop, _ = await sign_in(client)
    phone, _ = await sign_in(client)  # same user, second device

    response = await client.post("/api/v1/auth/logout", headers=bearer(laptop))

    assert response.status_code == 204
    assert (await client.get("/api/v1/users/me", headers=bearer(laptop))).status_code == 401
    assert (await client.get("/api/v1/users/me", headers=bearer(phone))).status_code == 200


async def test_logout_requires_auth(client: AsyncClient) -> None:
    assert (await client.post("/api/v1/auth/logout")).status_code == 401
