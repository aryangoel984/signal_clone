from sqlalchemy import CheckConstraint, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import SQLITE_TABLE_ARGS, Base, CreatedAtMixin


class Block(CreatedAtMixin, Base):
    """`blocker` blocked `blocked`. Separate from contacts so anyone can be blocked (PLAN 7.2)."""

    __tablename__ = "blocks"
    __table_args__ = (
        CheckConstraint("blocker_id <> blocked_id", name="not_self"),
        Index("ix_blocks_blocked_id", "blocked_id"),
        SQLITE_TABLE_ARGS,
    )

    blocker_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    blocked_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
