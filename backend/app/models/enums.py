from enum import StrEnum

from sqlalchemy import Enum


class ConversationType(StrEnum):
    DIRECT = "direct"
    GROUP = "group"


class MemberRole(StrEnum):
    ADMIN = "admin"
    MEMBER = "member"


class MessageKind(StrEnum):
    TEXT = "text"
    SYSTEM = "system"


class Theme(StrEnum):
    SYSTEM = "system"
    LIGHT = "light"
    DARK = "dark"


class MessageStatus(StrEnum):
    """Computed from receipts, never stored. `sending` exists only on the client."""

    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"


def enum_column(enum_class: type[StrEnum], name: str) -> Enum:
    """TEXT column with a CHECK constraint that stores the enum's lowercase *values*
    ('direct'), not its member names ('DIRECT'), which SQLAlchemy would use by default."""
    return Enum(
        enum_class,
        name=name,
        native_enum=False,
        create_constraint=True,
        values_callable=lambda members: [member.value for member in members],
        validate_strings=True,
    )
