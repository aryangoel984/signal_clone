from sqlalchemy import CheckConstraint, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import SQLITE_TABLE_ARGS, Base, TimestampMixin


class Contact(TimestampMixin, Base):
    """One-directional address book entry: `owner` saved `contact_user`."""

    __tablename__ = "contacts"
    __table_args__ = (
        CheckConstraint("owner_id <> contact_user_id", name="not_self"),
        Index("ix_contacts_contact_user_id", "contact_user_id"),
        SQLITE_TABLE_ARGS,
    )

    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    contact_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    nickname: Mapped[str | None]
