from datetime import datetime

from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import SQLITE_TABLE_ARGS, Base, CreatedAtMixin


class UserSession(CreatedAtMixin, Base):
    """A login session (table `sessions`). Named to avoid confusion with SQLAlchemy's AsyncSession."""

    __tablename__ = "sessions"
    __table_args__ = (
        Index("ix_sessions_user_id", "user_id"),
        SQLITE_TABLE_ARGS,
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(unique=True)  # SHA-256 of the token; the raw token is never stored
    expires_at: Mapped[datetime]
    last_used_at: Mapped[datetime]
