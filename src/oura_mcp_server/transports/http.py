from __future__ import annotations

from oura_mcp_server.admin.routes import register_admin_routes
from oura_mcp_server.auth.api_key_auth import ApiKeyAuthProvider
from oura_mcp_server.auth.token_store import TokenStore
from oura_mcp_server.config import Settings
from oura_mcp_server.core.server import create_mcp_server
from oura_mcp_server.core.web_routes import register_web_routes


def build_http_server(settings: Settings):
    """Construye el FastMCP para HTTP: protocolo MCP en /mcp + rutas OAuth/webhooks
    + panel de administracion, con auth Bearer multi-usuario."""
    store = TokenStore(settings.token_db_path)
    auth = ApiKeyAuthProvider()
    mcp = create_mcp_server(settings, store, auth=auth)
    register_web_routes(mcp, settings, store)
    register_admin_routes(mcp, settings, store)
    return mcp


def run_http(settings: Settings, host: str, port: int) -> None:
    mcp = build_http_server(settings)
    mcp.run(transport="http", host=host, port=port)
