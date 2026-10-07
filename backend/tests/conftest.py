from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import Database, create_database, init_db
from app.main import create_app

TEST_ORIGIN = "http://localhost:3000"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    # A real file, not :memory: - each pooled connection to :memory: would get its own
    # empty database, and WAL mode doesn't apply to in-memory databases.
    return Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        uploads_dir=tmp_path / "uploads",
        cors_origins=[TEST_ORIGIN],
        demo_bots_enabled=False,
    )


@pytest.fixture
async def database(settings: Settings) -> AsyncIterator[Database]:
    """Built with the app's own factory, so tests exercise the real pragma listener."""
    db = create_database(settings.database_url)
    await init_db(db)
    yield db
    await db.engine.dispose()


@pytest.fixture
async def session(database: Database) -> AsyncIterator[AsyncSession]:
    async with database.session_factory() as db_session:
        yield db_session


@pytest.fixture
async def client(settings: Settings, database: Database) -> AsyncIterator[AsyncClient]:
    """HTTP client against the real app, with its lifespan (init_db on startup) running."""
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http_client:
            yield http_client


async def sign_in(client: AsyncClient, phone_number: str = "+15557770001") -> tuple[str, dict[str, Any]]:
    """Verifies a number and returns (token, response body)."""
    response = await client.post("/api/v1/auth/otp/verify", json={"phone_number": phone_number, "code": "123456"})
    assert response.status_code == 200, response.text
    body = response.json()
    return body["token"], body


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
