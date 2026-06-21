from pathlib import Path

from oura_mcp_server.config import Settings
from oura_mcp_server.auth.token_store import TokenStore
from oura_mcp_server.core.server import create_mcp_server


def test_create_mcp_server_with_bearer(tmp_path: Path) -> None:
    settings = Settings(oura_bearer_token="test-token", token_db_path=tmp_path / "db.sqlite3")
    store = TokenStore(settings.token_db_path)
    mcp = create_mcp_server(settings, store)
    assert mcp is not None
    assert mcp.name == "oura-mcp-server"


def test_create_mcp_server_without_auth(tmp_path: Path) -> None:
    settings = Settings(token_db_path=tmp_path / "db.sqlite3")
    store = TokenStore(settings.token_db_path)
    mcp = create_mcp_server(settings, store)
    assert mcp is not None


def test_token_expiry() -> None:
    from datetime import datetime, timedelta, timezone
    from oura_mcp_server.models import OAuthTokens

    old = OAuthTokens(
        access_token="old",
        expires_in=1,
        created_at=datetime.now(timezone.utc) - timedelta(hours=2),
    )
    assert old.is_expired()

    fresh = OAuthTokens(access_token="fresh", expires_in=3600)
    assert not fresh.is_expired()
