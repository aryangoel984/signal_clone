from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """App configuration, read from environment variables and `backend/.env`."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///./app.db"
    uploads_dir: Path = Path("uploads")
    session_ttl_days: int = 30
    cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=lambda: ["http://localhost:3000"])
    demo_bots_enabled: bool = True
    demo_bot_phones: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["+15550000001", "+15550000002"]
    )
    demo_bot_delay_scale: float = 1.0  # multiplies the bots' delays; 0 in tests

    @field_validator("cors_origins", "demo_bot_phones", mode="before")
    @classmethod
    def split_comma_separated(cls, value: object) -> object:
        """Allow `A,B,C` in env vars instead of JSON arrays."""
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
