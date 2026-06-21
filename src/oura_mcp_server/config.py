from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "oura-mcp-server"
    log_level: str = "INFO"

    # OAuth2 (produccion)
    oura_client_id: str | None = None
    oura_client_secret: str | None = None
    oura_redirect_uri: str = "http://127.0.0.1:8000/auth/callback"
    oura_scopes: str = "email personal daily"

    # Dev fallback
    oura_bearer_token: str | None = None

    # Storage
    token_db_path: Path = Path("./data/tokens.sqlite3")

    # Oura API
    oura_api_base: str = "https://api.ouraring.com/v2"

    # HTTP transport
    http_host: str = "127.0.0.1"
    http_port: int = 8000

    # MCP
    mcp_name: str = "oura-mcp-server"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
