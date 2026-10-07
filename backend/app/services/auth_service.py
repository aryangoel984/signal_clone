from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.avatar_colors import avatar_color_for
from app.core.security import generate_session_token, hash_session_token, is_valid_otp
from app.core.time import utc_now
from app.models import User, UserSession, UserSettings

# Avoid a DB write on every request: last_used_at only needs to be roughly right.
LAST_USED_RESOLUTION = timedelta(hours=1)


class InvalidOtpError(Exception):
    pass


@dataclass(frozen=True)
class SignInResult:
    token: str
    user: User
    is_new_user: bool


async def verify_otp(session: AsyncSession, phone_number: str, code: str, session_ttl: timedelta) -> SignInResult:
    """Signal-style: there is no separate sign-up. Verifying an unknown number creates
    the account (display_name stays NULL until onboarding); a known number logs in."""
    if not is_valid_otp(code):
        raise InvalidOtpError

    user, is_new_user = await _get_or_create_user(session, phone_number)
    token = generate_session_token()
    now = utc_now()
    session.add(
        UserSession(
            user_id=user.id,
            token_hash=hash_session_token(token),
            expires_at=now + session_ttl,
            last_used_at=now,
        )
    )
    await session.commit()
    return SignInResult(token=token, user=user, is_new_user=is_new_user)


async def _get_or_create_user(session: AsyncSession, phone_number: str) -> tuple[User, bool]:
    existing = await session.scalar(select(User).where(User.phone_number == phone_number))
    if existing is not None:
        return existing, False

    user = User(phone_number=phone_number, avatar_color=avatar_color_for(phone_number))
    session.add(user)
    try:
        await session.flush()
    except IntegrityError:
        # Two verify requests for the same new number raced; the other one created it.
        await session.rollback()
        return (await session.execute(select(User).where(User.phone_number == phone_number))).scalar_one(), False
    session.add(UserSettings(user_id=user.id))
    return user, True


async def authenticate(session: AsyncSession, token: str) -> tuple[UserSession, User] | None:
    """Returns the session and its user, or None if the token is unknown or expired."""
    row = (
        await session.execute(
            select(UserSession, User)
            .join(User, User.id == UserSession.user_id)
            .where(UserSession.token_hash == hash_session_token(token))
        )
    ).one_or_none()
    if row is None:
        return None

    user_session, user = row
    now = utc_now()
    if user_session.expires_at <= now:
        return None
    if now - user_session.last_used_at > LAST_USED_RESOLUTION:
        user_session.last_used_at = now
        await session.commit()
    return user_session, user


async def logout(session: AsyncSession, user_session: UserSession) -> None:
    """Revokes only this session; the user's other devices stay signed in."""
    await session.delete(user_session)
    await session.commit()
