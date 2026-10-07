from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import get_db
from app.models import User, UserSession
from app.services import auth_service

DbSession = Annotated[AsyncSession, Depends(get_db)]

_bearer = HTTPBearer(auto_error=False)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_session(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> tuple[UserSession, User]:
    if credentials is None:
        raise _unauthorized("Not authenticated")
    result = await auth_service.authenticate(db, credentials.credentials)
    if result is None:
        raise _unauthorized("Session expired or invalid")
    return result


CurrentSession = Annotated[tuple[UserSession, User], Depends(get_current_session)]


async def get_current_user(current: CurrentSession) -> User:
    return current[1]


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_settings_from_app(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


AppSettings = Annotated[Settings, Depends(get_settings_from_app)]
