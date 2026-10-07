from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import SQLITE_TABLE_ARGS, Base, TimestampMixin


class Reaction(TimestampMixin, Base):
    """One reaction per user per message, as in Signal; reacting again replaces it."""

    __tablename__ = "reactions"
    __table_args__ = (SQLITE_TABLE_ARGS,)

    message_id: Mapped[int] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    emoji: Mapped[str]
