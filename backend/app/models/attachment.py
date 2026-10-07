from sqlalchemy import CheckConstraint, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import SQLITE_TABLE_ARGS, Base, CreatedAtMixin

MAX_ATTACHMENT_BYTES = 25 * 1024 * 1024


class Attachment(CreatedAtMixin, Base):
    __tablename__ = "attachments"
    __table_args__ = (
        CheckConstraint(f"size_bytes <= {MAX_ATTACHMENT_BYTES}", name="max_size"),
        Index("ix_attachments_message_id", "message_id"),
        SQLITE_TABLE_ARGS,
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # NULL between upload and send, so the composer can show a preview first.
    message_id: Mapped[int | None] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"))
    uploader_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    file_name: Mapped[str]
    mime_type: Mapped[str]
    size_bytes: Mapped[int]
    storage_path: Mapped[str]  # file lives on disk under backend/uploads/, not in SQLite
    width: Mapped[int | None]
    height: Mapped[int | None]
