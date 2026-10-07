from datetime import datetime
from typing import Any

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.time import UTCDateTime, utc_now

# Predictable names for every constraint and index (also what a future Alembic setup needs).
NAMING_CONVENTION = {
    "pk": "pk_%(table_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
}

# Added to every table's __table_args__. SQLAlchemy emits AUTOINCREMENT only for a single
# integer, non-FK primary key, so on composite/FK-keyed tables this is a harmless no-op.
# On tables with a surrogate id it stops SQLite from reusing ids of deleted rows.
SQLITE_TABLE_ARGS: dict[str, Any] = {"sqlite_autoincrement": True}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map = {datetime: UTCDateTime()}


class CreatedAtMixin:
    created_at: Mapped[datetime] = mapped_column(default=utc_now)


class TimestampMixin(CreatedAtMixin):
    updated_at: Mapped[datetime] = mapped_column(default=utc_now, onupdate=utc_now)
