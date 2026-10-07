from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from fastapi import Request
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.models import Base


def _set_sqlite_pragmas(dbapi_connection: Any, _connection_record: Any) -> None:
    """Runs on every new DB connection. A plain (sync) function because SQLAlchemy's
    pool events fire on the sync engine; with aiosqlite, `dbapi_connection` is
    SQLAlchemy's sync-style adapter around the async connection."""
    cursor = dbapi_connection.cursor()
    try:
        # First, so the pragmas below wait for a lock instead of failing with "database is locked".
        cursor.execute("PRAGMA busy_timeout=5000")
        # Per-connection and off by default in SQLite; without it ON DELETE rules are ignored.
        cursor.execute("PRAGMA foreign_keys=ON")
        # Readers don't block the writer. Persisted in the file; re-setting is a no-op.
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
    finally:
        cursor.close()


@dataclass(frozen=True)
class Database:
    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]


def create_database(url: str) -> Database:
    engine = create_async_engine(url)
    event.listen(engine.sync_engine, "connect", _set_sqlite_pragmas)
    # expire_on_commit=False: services read objects after commit (responses, WS events);
    # an expired attribute would trigger hidden async I/O and raise MissingGreenlet.
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    return Database(engine=engine, session_factory=session_factory)


async def init_db(database: Database) -> None:
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def drop_db(database: Database) -> None:
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one session per request. Services commit explicitly."""
    database: Database = request.app.state.db
    async with database.session_factory() as session:
        yield session
