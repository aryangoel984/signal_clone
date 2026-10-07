from sqlalchemy import ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import SQLITE_TABLE_ARGS, Base, TimestampMixin
from app.models.enums import Theme, enum_column


class UserSettings(TimestampMixin, Base):
    __tablename__ = "user_settings"
    __table_args__ = (SQLITE_TABLE_ARGS,)

    # The FK doubles as the PK, which enforces one settings row per user.
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    theme: Mapped[Theme] = mapped_column(
        enum_column(Theme, "theme"), default=Theme.SYSTEM, server_default=Theme.SYSTEM.value
    )
    read_receipts_enabled: Mapped[bool] = mapped_column(default=True, server_default=text("1"))
    typing_indicators_enabled: Mapped[bool] = mapped_column(default=True, server_default=text("1"))
    notifications_enabled: Mapped[bool] = mapped_column(default=True, server_default=text("1"))
    enter_key_sends: Mapped[bool] = mapped_column(default=True, server_default=text("1"))
