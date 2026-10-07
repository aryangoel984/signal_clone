import secrets
from pathlib import Path

from anyio import Path as AsyncPath
from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.schemas.user import UpdateMeRequest

MAX_AVATAR_BYTES = 5 * 1024 * 1024
MEDIA_URL_PREFIX = "/media/"
_READ_CHUNK = 64 * 1024


class UsernameTakenError(Exception):
    pass


class AvatarTooLargeError(Exception):
    pass


class UnsupportedImageError(Exception):
    pass


async def update_profile(session: AsyncSession, user: User, changes: UpdateMeRequest) -> User:
    fields = changes.model_dump(exclude_unset=True)
    new_username = fields.get("username")
    if new_username is not None and new_username != user.username:
        taken = await session.scalar(select(User.id).where(User.username == new_username, User.id != user.id))
        if taken is not None:
            raise UsernameTakenError
    for name, value in fields.items():
        setattr(user, name, value)
    await session.commit()
    return user


def detect_image_extension(header: bytes) -> str | None:
    """Identify the format from the file's first bytes; the client's Content-Type is not trusted."""
    if header.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return "webp"
    return None  # anything else, including SVG (which can carry scripts), is rejected


async def set_avatar(session: AsyncSession, user: User, upload: UploadFile, uploads_dir: Path) -> User:
    data = await _read_limited(upload, MAX_AVATAR_BYTES)
    extension = detect_image_extension(data[:16])
    if extension is None:
        raise UnsupportedImageError

    avatars_dir = AsyncPath(uploads_dir) / "avatars"
    await avatars_dir.mkdir(parents=True, exist_ok=True)
    # Random, server-chosen name: never user-controlled, and a new URL busts browser caches.
    file_name = f"{user.id}-{secrets.token_hex(8)}.{extension}"
    await (avatars_dir / file_name).write_bytes(data)

    old_url = user.avatar_url
    user.avatar_url = f"{MEDIA_URL_PREFIX}avatars/{file_name}"
    await session.commit()
    await _delete_media_file(old_url, uploads_dir)
    return user


async def remove_avatar(session: AsyncSession, user: User, uploads_dir: Path) -> User:
    old_url = user.avatar_url
    user.avatar_url = None
    await session.commit()
    await _delete_media_file(old_url, uploads_dir)
    return user


async def _read_limited(upload: UploadFile, max_bytes: int) -> bytes:
    """Reads in chunks and stops as soon as the limit is passed, so a huge upload
    is never held in memory."""
    chunks: list[bytes] = []
    total = 0
    while chunk := await upload.read(_READ_CHUNK):
        total += len(chunk)
        if total > max_bytes:
            raise AvatarTooLargeError
        chunks.append(chunk)
    return b"".join(chunks)


async def _delete_media_file(media_url: str | None, uploads_dir: Path) -> None:
    if media_url is None or not media_url.startswith(MEDIA_URL_PREFIX):
        return
    root = uploads_dir.resolve()
    path = (root / media_url.removeprefix(MEDIA_URL_PREFIX)).resolve()
    if path.is_relative_to(root):  # never delete outside the uploads directory
        await AsyncPath(path).unlink(missing_ok=True)
