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
    # Identificadores reales de los scopes de la API v2 (los mismos que se
    # marcan en la app de Oura). Ojo: es `spo2`, no `spo2Daily` — Oura descarta
    # los nombres que no reconoce sin avisar.
    oura_scopes: str = (
        "email personal daily heartrate workout tag session "
        "spo2 stress heart_health ring_configuration"
    )

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
    # Token de verificacion de los webhooks: el mismo que se registra al crear
    # la suscripcion. Sin el, /webhooks/oura falla cerrado (503).
    oura_webhook_verification_token: str | None = None
    # Panel de administracion (/admin/*): password compartido, un solo admin.
    admin_password: str | None = None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
