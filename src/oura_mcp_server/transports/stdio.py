from __future__ import annotations

from oura_mcp_server.auth.token_store import TokenStore
from oura_mcp_server.config import Settings
from oura_mcp_server.core.server import create_mcp_server


def run_stdio(settings: Settings) -> None:
    """Transporte stdio (local, portable). Sin auth: usa default_user_id / bearer."""
    store = TokenStore(settings.token_db_path)
    mcp = create_mcp_server(settings, store, auth=None)
    mcp.run()
