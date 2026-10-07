from httpx import AsyncClient

from tests.conftest import TEST_ORIGIN


async def test_health_returns_ok(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_cors_allows_configured_origin(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health", headers={"Origin": TEST_ORIGIN})

    assert response.headers["access-control-allow-origin"] == TEST_ORIGIN


async def test_cors_rejects_unknown_origin(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health", headers={"Origin": "http://evil.example"})

    assert "access-control-allow-origin" not in response.headers
