from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, UserSettings
from app.schemas.settings import UpdateSettingsRequest


async def get_settings(session: AsyncSession, user: User) -> UserSettings:
    settings = await session.get(UserSettings, user.id)
    if settings is None:  # created at signup; this only covers rows made before that existed
        settings = UserSettings(user_id=user.id)
        session.add(settings)
        await session.commit()
    return settings


async def update_settings(session: AsyncSession, user: User, changes: UpdateSettingsRequest) -> UserSettings:
    settings = await get_settings(session, user)
    for name, value in changes.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(settings, name, value)
    await session.commit()
    return settings
