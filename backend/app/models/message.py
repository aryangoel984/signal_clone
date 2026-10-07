from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, CheckConstraint, ForeignKey, Index, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import SQLITE_TABLE_ARGS, Base, CreatedAtMixin
from app.models.enums import MessageKind, enum_column

if TYPE_CHECKING:
    from app.models.attachment import Attachment
    from app.models.user import User


class Message(CreatedAtMixin, Base):
    __tablename__ = "messages"
    __table_args__ = (
        # Idempotent retries: a client resending the same client_id gets the existing row.
        UniqueConstraint("sender_id", "client_id"),
        CheckConstraint("kind = 'system' OR system_data IS NULL", name="system_data_only_on_system"),
        # Serves pagination, reconnect sync, last-message preview and unread counts.
        Index("ix_messages_conversation_id_id", "conversation_id", "id"),
        Index("ix_messages_expires_at", "expires_at", sqlite_where=text("expires_at IS NOT NULL")),
        SQLITE_TABLE_ARGS,
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"))
    # Nullable + SET NULL keeps group history when a user is deleted ("Deleted user").
    # So there is intentionally no CHECK that text messages have a sender.
    sender_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    kind: Mapped[MessageKind] = mapped_column(
        enum_column(MessageKind, "kind"), default=MessageKind.TEXT, server_default=MessageKind.TEXT.value
    )
    body: Mapped[str]  # message text, or the event name for system messages
    system_data: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    client_id: Mapped[str | None]
    reply_to_id: Mapped[int | None] = mapped_column(ForeignKey("messages.id", ondelete="SET NULL"))
    expires_at: Mapped[datetime | None]
    deleted_at: Mapped[datetime | None]

    sender: Mapped["User | None"] = relationship(lazy="raise")
    attachments: Mapped[list["Attachment"]] = relationship(lazy="raise", passive_deletes=True)
