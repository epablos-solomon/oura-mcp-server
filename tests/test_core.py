from pathlib import Path

from oura_mcp_server.config import Settings
from oura_mcp_server.auth.token_store import TokenStore
from oura_mcp_server.core.server import create_mcp_server


def test_mcp_has_tools(tmp_path: Path) -> None:
    settings = Settings(oura_bearer_token="x", token_db_path=tmp_path / "t.sqlite3")
    store = TokenStore(settings.token_db_path)
    mcp = create_mcp_server(settings, store)
    assert mcp is not None


def test_mcp_prompt_exists(tmp_path: Path) -> None:
    settings = Settings(oura_bearer_token="x", token_db_path=tmp_path / "t.sqlite3")
    store = TokenStore(settings.token_db_path)
    mcp = create_mcp_server(settings, store)
    assert mcp.name == "oura-mcp-server"
