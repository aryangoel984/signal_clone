from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_uploads_dir_is_created_on_a_fresh_volume(tmp_path: Path) -> None:
    """First boot on an empty /data: the nested uploads folder doesn't exist yet."""
    uploads = tmp_path / "data" / "uploads"
    assert not uploads.exists()

    app = create_app(Settings(database_url=f"sqlite+aiosqlite:///{tmp_path / 'data' / 'app.db'}", uploads_dir=uploads))
    (uploads / "probe.txt").write_text("ok")

    assert uploads.is_dir()
    with TestClient(app) as client:
        response = client.get("/media/probe.txt")
    assert response.status_code == 200 and response.text == "ok"


def test_cors_origins_are_split_and_trailing_slashes_dropped() -> None:
    settings = Settings.model_validate({"cors_origins": "https://signal.vercel.app/, http://localhost:3000"})

    assert settings.cors_origins == ["https://signal.vercel.app", "http://localhost:3000"]


async def test_database_folder_is_created_on_a_fresh_volume(tmp_path: Path) -> None:
    from app.core.db import create_database, init_db

    database_file = tmp_path / "data" / "app.db"
    database = create_database(f"sqlite+aiosqlite:///{database_file}")
    try:
        await init_db(database)
    finally:
        await database.engine.dispose()

    assert database_file.is_file()
