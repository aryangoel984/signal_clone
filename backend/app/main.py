from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import Settings, get_settings
from app.core.db import Database, create_database, init_db
from app.core.media import MediaFiles
from app.routers import auth, contacts, conversations, health, messages, users, ws
from app.services.demo_bot import DemoBots
from app.ws.manager import ConnectionManager
from app.ws.realtime import Realtime

API_PREFIX = "/api/v1"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    database: Database = app.state.db
    await init_db(database)
    bots: DemoBots | None = app.state.demo_bots
    if bots is not None:
        await bots.load()
    yield
    if bots is not None:
        await bots.shutdown()
    await app.state.realtime.shutdown()
    await database.engine.dispose()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="Signal Clone API", lifespan=lifespan)
    app.state.settings = settings
    app.state.db = create_database(settings.database_url)
    app.state.realtime = Realtime(ConnectionManager(), app.state.db.session_factory)
    app.state.demo_bots = None
    if settings.demo_bots_enabled:
        bots = DemoBots(app.state.realtime, app.state.db.session_factory, settings.demo_bot_phones, settings.demo_bot_delay_scale)
        app.state.realtime.message_hooks.append(bots.on_message)
        app.state.demo_bots = bots

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        # Auth is a Bearer header, not a cookie, so credentials mode is not needed.
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    app.include_router(health.router, prefix=API_PREFIX)
    app.include_router(auth.router, prefix=API_PREFIX)
    app.include_router(users.router, prefix=API_PREFIX)
    app.include_router(contacts.router, prefix=API_PREFIX)
    app.include_router(conversations.router, prefix=API_PREFIX)
    app.include_router(messages.router, prefix=API_PREFIX)
    app.include_router(ws.router)

    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/media", MediaFiles(directory=settings.uploads_dir), name="media")
    return app


app = create_app()
