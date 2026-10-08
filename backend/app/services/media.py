"""Uploaded images (user and group avatars): validation, storage under UPLOADS_DIR, deletion."""

import secrets
from pathlib import Path

from anyio import Path as AsyncPath
from fastapi import UploadFile

MAX_IMAGE_BYTES = 5 * 1024 * 1024
MEDIA_URL_PREFIX = "/media/"
_READ_CHUNK = 64 * 1024


class ImageTooLargeError(Exception):
    pass


class UnsupportedImageError(Exception):
    pass


def detect_image_extension(header: bytes) -> str | None:
    """Identify the format from the file's first bytes; the client's Content-Type is not trusted."""
    if header.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return "webp"
    return None  # anything else, including SVG (which can carry scripts), is rejected


async def save_image(upload: UploadFile, uploads_dir: Path, folder: str, name_prefix: str) -> str:
    """Validates and stores an image; returns its media URL (`/media/<folder>/<file>`).
    The file name is random and server-chosen: never user-controlled, and a new URL
    busts browser caches."""
    data = await _read_limited(upload, MAX_IMAGE_BYTES)
    extension = detect_image_extension(data[:16])
    if extension is None:
        raise UnsupportedImageError
    directory = AsyncPath(uploads_dir) / folder
    await directory.mkdir(parents=True, exist_ok=True)
    file_name = f"{name_prefix}-{secrets.token_hex(8)}.{extension}"
    await (directory / file_name).write_bytes(data)
    return f"{MEDIA_URL_PREFIX}{folder}/{file_name}"


async def delete_media(media_url: str | None, uploads_dir: Path) -> None:
    if media_url is None or not media_url.startswith(MEDIA_URL_PREFIX):
        return
    root = uploads_dir.resolve()
    path = (root / media_url.removeprefix(MEDIA_URL_PREFIX)).resolve()
    if path.is_relative_to(root):  # never delete outside the uploads directory
        await AsyncPath(path).unlink(missing_ok=True)


async def _read_limited(upload: UploadFile, max_bytes: int) -> bytes:
    """Reads in chunks and stops as soon as the limit is passed, so a huge upload is
    never held in memory."""
    chunks: list[bytes] = []
    total = 0
    while chunk := await upload.read(_READ_CHUNK):
        total += len(chunk)
        if total > max_bytes:
            raise ImageTooLargeError
        chunks.append(chunk)
    return b"".join(chunks)
