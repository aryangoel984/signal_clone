from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.main import create_app

TEST_ORIGIN = "http://localhost:3000"


@pytest.fixture
def settings() -> Settings:
    return Settings(cors_origins=[TEST_ORIGIN], demo_bots_enabled=False)


@pytest.fixture
async def client(settings: Settings) -> AsyncIterator[AsyncClient]:
    app = create_app(settings)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
