from collections.abc import AsyncIterator
from pathlib import Path

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
async def client(settings: Settings) -> AsyncIterator[AsyncClient]:
    app = create_app(settings)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http_client:
        yield http_client
