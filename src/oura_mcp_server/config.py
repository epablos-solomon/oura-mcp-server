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
    # Scopes que cubren toda la informacion disponible de la API v2 de Oura.
    oura_scopes: str = "email personal daily heartrate workout tag session spo2Daily"

    # Dev fallback (un solo usuario; ignora multi-tenant)
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

    # Multi-tenant / identidad (transporte http)
    tenants_config_path: str = "./config/tenants.yaml"
    default_tenant_id: str = "default"
    # user_id usado cuando no hay autenticacion (stdio o bearer dev)
    default_user_id: str = "default"
    # Secreto para firmar el parametro `state` del flujo OAuth.
    oura_state_secret: str | None = None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
