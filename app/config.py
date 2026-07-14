"""Application configuration loaded from environment / .env."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. All values are overridable via PULLVID_* env vars."""

    model_config = SettingsConfigDict(
        env_prefix="PULLVID_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: str = "0.0.0.0"
    port: int = 8000
    # NoDecode: skip pydantic-settings' JSON pre-parse so a comma-separated env
    # string (e.g. "https://a.com,https://b.com") reaches the validator below
    # instead of failing as invalid JSON.
    cors_origins: Annotated[list[str], NoDecode] = [
        "https://hoist.knightdeveloper.com",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ]
    download_dir: str = "./downloads"
    cookies_file: str | None = None
    max_duration_seconds: int = 7200
    cleanup_after_seconds: int = 3600
    playlist_max: int = 50

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: object) -> object:
        """Accept a comma-separated string from the env and split into a list."""
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("cookies_file", mode="before")
    @classmethod
    def _empty_cookies_to_none(cls, value: object) -> object:
        """Treat an empty PULLVID_COOKIES_FILE as unset."""
        if isinstance(value, str) and not value.strip():
            return None
        return value


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
