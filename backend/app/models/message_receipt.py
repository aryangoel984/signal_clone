from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import SQLITE_TABLE_ARGS, Base, CreatedAtMixin


class MessageReceipt(CreatedAtMixin, Base):
    """Delivery/read state of one message for one recipient (never the sender)."""

    __tablename__ = "message_receipts"
    __table_args__ = (
        CheckConstraint("read_at IS NULL OR delivered_at IS NOT NULL", name="read_implies_delivered"),
        # Partial index: on connect, find a user's pending deliveries without scanning delivered rows.
        Index("ix_receipts_user_undelivered", "user_id", sqlite_where=text("delivered_at IS NULL")),
        SQLITE_TABLE_ARGS,
    )

    message_id: Mapped[int] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    delivered_at: Mapped[datetime | None]
    read_at: Mapped[datetime | None]  # stays NULL when the reader has read receipts off (PLAN 7.4)
