from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import Database
from app.models import Base


async def test_pragmas_are_set_on_every_connection(database: Database) -> None:
    # Two separate connections from the pool: the listener must have run on each.
    for _ in range(2):
        async with database.engine.connect() as connection:
            assert (await connection.execute(text("PRAGMA busy_timeout"))).scalar_one() == 5000
            assert (await connection.execute(text("PRAGMA foreign_keys"))).scalar_one() == 1
            assert (await connection.execute(text("PRAGMA journal_mode"))).scalar_one() == "wal"


def test_every_table_sets_sqlite_autoincrement() -> None:
    missing = [
        table.name for table in Base.metadata.sorted_tables if table.dialect_options["sqlite"]["autoincrement"] is not True
    ]
    assert missing == []


async def test_autoincrement_emitted_exactly_for_surrogate_id_tables(session: AsyncSession) -> None:
    rows = (await session.execute(text("SELECT name, sql FROM sqlite_master WHERE type = 'table'"))).all()
    with_autoincrement = {name for name, sql in rows if "AUTOINCREMENT" in sql}

    assert with_autoincrement == {"users", "sessions", "conversations", "messages", "attachments"}
