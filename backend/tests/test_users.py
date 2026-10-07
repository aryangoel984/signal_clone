import pytest
from httpx import AsyncClient, Response

from app.core.config import Settings
from tests.conftest import bearer, sign_in

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 64
WEBP_BYTES = b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"\x00" * 64


async def upload(client: AsyncClient, token: str, content: bytes, content_type: str = "image/png") -> Response:
    return await client.put(
        "/api/v1/users/me/avatar",
        headers=bearer(token),
        files={"file": ("avatar.png", content, content_type)},
    )


# --- profile --------------------------------------------------------------------------


async def test_onboarding_sets_trimmed_display_name(client: AsyncClient) -> None:
    token, _ = await sign_in(client)

    response = await client.patch("/api/v1/users/me", headers=bearer(token), json={"display_name": "  Sam Lee  "})

    assert response.status_code == 200
    assert response.json()["display_name"] == "Sam Lee"


@pytest.mark.parametrize("name", ["", "   ", "x" * 65])
async def test_invalid_display_name_is_rejected(client: AsyncClient, name: str) -> None:
    token, _ = await sign_in(client)

    response = await client.patch("/api/v1/users/me", headers=bearer(token), json={"display_name": name})

    assert response.status_code == 422


async def test_patch_only_changes_sent_fields(client: AsyncClient) -> None:
    token, _ = await sign_in(client)
    await client.patch("/api/v1/users/me", headers=bearer(token), json={"display_name": "Sam", "about": "Hi"})

    response = await client.patch("/api/v1/users/me", headers=bearer(token), json={"about": "Busy"})

    assert response.json()["display_name"] == "Sam"
    assert response.json()["about"] == "Busy"


async def test_username_is_lowercased_and_unique(client: AsyncClient) -> None:
    first, _ = await sign_in(client, "+15557770001")
    second, _ = await sign_in(client, "+15557770002")

    taken = await client.patch("/api/v1/users/me", headers=bearer(first), json={"username": "Sam.Lee"})
    clash = await client.patch("/api/v1/users/me", headers=bearer(second), json={"username": "sam.lee"})

    assert taken.json()["username"] == "sam.lee"
    assert clash.status_code == 409


async def test_unknown_profile_field_is_rejected(client: AsyncClient) -> None:
    token, _ = await sign_in(client)

    response = await client.patch("/api/v1/users/me", headers=bearer(token), json={"phone_number": "+15550000000"})

    assert response.status_code == 422


# --- avatar ---------------------------------------------------------------------------


@pytest.mark.parametrize(("content", "extension"), [(PNG_BYTES, "png"), (JPEG_BYTES, "jpg"), (WEBP_BYTES, "webp")])
async def test_avatar_upload_is_stored_and_served_with_nosniff(
    client: AsyncClient, settings: Settings, content: bytes, extension: str
) -> None:
    token, _ = await sign_in(client)

    response = await upload(client, token, content)

    assert response.status_code == 200
    avatar_url: str = response.json()["avatar_url"]
    assert avatar_url.startswith("/media/avatars/") and avatar_url.endswith(f".{extension}")
    assert (settings.uploads_dir / avatar_url.removeprefix("/media/")).read_bytes() == content
    served = await client.get(avatar_url)
    assert served.status_code == 200
    assert served.content == content
    assert served.headers["x-content-type-options"] == "nosniff"


async def test_spoofed_content_type_is_rejected(client: AsyncClient) -> None:
    token, _ = await sign_in(client)

    response = await upload(client, token, b"<svg onload=alert(1)></svg>", content_type="image/png")

    assert response.status_code == 415


async def test_oversized_avatar_is_rejected(client: AsyncClient) -> None:
    token, _ = await sign_in(client)

    response = await upload(client, token, PNG_BYTES + b"\x00" * (5 * 1024 * 1024))

    assert response.status_code == 413


async def test_replacing_avatar_deletes_old_file(client: AsyncClient, settings: Settings) -> None:
    token, _ = await sign_in(client)
    first_url: str = (await upload(client, token, PNG_BYTES)).json()["avatar_url"]
    first_path = settings.uploads_dir / first_url.removeprefix("/media/")

    second_url: str = (await upload(client, token, JPEG_BYTES)).json()["avatar_url"]

    assert second_url != first_url
    assert not first_path.exists()
    assert (await client.get(first_url)).status_code == 404


async def test_removing_avatar_deletes_file(client: AsyncClient, settings: Settings) -> None:
    token, _ = await sign_in(client)
    url: str = (await upload(client, token, PNG_BYTES)).json()["avatar_url"]

    response = await client.delete("/api/v1/users/me/avatar", headers=bearer(token))

    assert response.json()["avatar_url"] is None
    assert not (settings.uploads_dir / url.removeprefix("/media/")).exists()


async def test_avatar_upload_requires_auth(client: AsyncClient) -> None:
    response = await client.put("/api/v1/users/me/avatar", files={"file": ("a.png", PNG_BYTES, "image/png")})

    assert response.status_code == 401
