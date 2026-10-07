from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import SQLITE_TABLE_ARGS, Base, TimestampMixin
from app.models.enums import ConversationType, enum_column

if TYPE_CHECKING:
    from app.models.conversation_member import ConversationMember


class Conversation(TimestampMixin, Base):
    __tablename__ = "conversations"
    __table_args__ = (
        CheckConstraint("(type = 'direct') = (direct_key IS NOT NULL)", name="direct_key_matches_type"),
        CheckConstraint("type = 'direct' OR name IS NOT NULL", name="group_has_name"),
        Index("ix_conversations_last_message_at", "last_message_at"),
        SQLITE_TABLE_ARGS,
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[ConversationType] = mapped_column(enum_column(ConversationType, "type"))
    name: Mapped[str | None]
    description: Mapped[str | None]
    avatar_url: Mapped[str | None]
    avatar_color: Mapped[str]
    # "{min_user_id}:{max_user_id}" for DMs: the DB guarantees one DM per pair.
    direct_key: Mapped[str | None] = mapped_column(unique=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    disappearing_seconds: Mapped[int | None]
    # Denormalized: updated with every new message so the chat list can sort cheaply.
    last_message_at: Mapped[datetime | None]

    members: Mapped[list["ConversationMember"]] = relationship(
        back_populates="conversation", lazy="raise", passive_deletes=True
    )
