from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    urja_portal_url: str = "https://urja-ops.flockenergy.tech"
    urja_username: str = "operator@urja.local"
    urja_password: str = "urja-ops-2026"

    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    cache_ttl_seconds: int = 300
    auto_sync_on_startup: bool = True
    session_refresh_buffer_seconds: int = 120

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
