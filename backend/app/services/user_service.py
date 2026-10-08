from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.schemas.user import UpdateMeRequest
from app.services.media import delete_media, save_image


class UsernameTakenError(Exception):
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


async def set_avatar(session: AsyncSession, user: User, upload: UploadFile, uploads_dir: Path) -> User:
    """Raises media.ImageTooLargeError / media.UnsupportedImageError for bad uploads."""
    url = await save_image(upload, uploads_dir, "avatars", str(user.id))
    old_url = user.avatar_url
    user.avatar_url = url
    await session.commit()
    await delete_media(old_url, uploads_dir)
    return user


async def remove_avatar(session: AsyncSession, user: User, uploads_dir: Path) -> User:
    old_url = user.avatar_url
    user.avatar_url = None
    await session.commit()
    await delete_media(old_url, uploads_dir)
    return user
