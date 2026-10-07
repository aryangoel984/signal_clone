from datetime import datetime

from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import SQLITE_TABLE_ARGS, Base, TimestampMixin


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (SQLITE_TABLE_ARGS,)

    id: Mapped[int] = mapped_column(primary_key=True)
    phone_number: Mapped[str] = mapped_column(unique=True)
    username: Mapped[str | None] = mapped_column(unique=True)
    display_name: Mapped[str | None]  # NULL until onboarding is finished
    about: Mapped[str | None]
    avatar_url: Mapped[str | None]
    avatar_color: Mapped[str]
    last_seen_at: Mapped[datetime | None]
