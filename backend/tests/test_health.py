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


async def test_cors_preflight_allows_authorization_header(client: AsyncClient) -> None:
    response = await client.options(
        "/api/v1/users/me",
        headers={
            "Origin": TEST_ORIGIN,
            "Access-Control-Request-Method": "PATCH",
            "Access-Control-Request-Headers": "authorization, content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == TEST_ORIGIN
    allowed_headers = {h.strip().lower() for h in response.headers["access-control-allow-headers"].split(",")}
    assert {"authorization", "content-type"} <= allowed_headers
    assert "PATCH" in response.headers["access-control-allow-methods"]
