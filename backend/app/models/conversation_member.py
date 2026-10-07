from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.time import utc_now
from app.models.base import SQLITE_TABLE_ARGS, Base, TimestampMixin
from app.models.enums import MemberRole, enum_column

if TYPE_CHECKING:
    from app.models.conversation import Conversation
    from app.models.user import User


class ConversationMember(TimestampMixin, Base):
    __tablename__ = "conversation_members"
    __table_args__ = (
        CheckConstraint("(left_at IS NULL) = (history_end_id IS NULL)", name="left_matches_history_end"),
        CheckConstraint("history_end_id IS NULL OR history_end_id >= history_start_id", name="history_range_valid"),
        Index("ix_members_user_id", "user_id"),
        SQLITE_TABLE_ARGS,
    )

    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role: Mapped[MemberRole] = mapped_column(
        enum_column(MemberRole, "role"), default=MemberRole.MEMBER, server_default=MemberRole.MEMBER.value
    )
    # Read watermark. Deliberately NOT a foreign key: the disappearing-message sweeper
    # deleting the watermark message must not reset it (PLAN 1.6).
    last_read_message_id: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    # Visible message range: id > history_start_id AND (history_end_id IS NULL OR id <= history_end_id).
    history_start_id: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    history_end_id: Mapped[int | None]
    is_pinned: Mapped[bool] = mapped_column(default=False, server_default=text("0"))
    is_archived: Mapped[bool] = mapped_column(default=False, server_default=text("0"))
    muted_until: Mapped[datetime | None]
    joined_at: Mapped[datetime] = mapped_column(default=utc_now)
    left_at: Mapped[datetime | None]  # soft removal; active member means left_at IS NULL

    conversation: Mapped["Conversation"] = relationship(back_populates="members", lazy="raise")
    user: Mapped["User"] = relationship(lazy="raise")
