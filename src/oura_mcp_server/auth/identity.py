"""Resolve the calling identity (oura_user_id) inside a tool invocation."""
from __future__ import annotations

from fastmcp.server.dependencies import get_access_token

from oura_mcp_server.config import Settings


def resolve_user_id(settings: Settings) -> str:
    """Returns the oura_user_id for the current caller.

    - HTTP transport: extracted from the validated Bearer token claims.
    - stdio / no auth: falls back to ``settings.default_user_id``.
    """
    try:
        token = get_access_token()
    except Exception:
        token = None
    if token is None:
        return settings.default_user_id
    claims = token.claims or {}
    return claims.get("oura_user_id") or claims.get("user") or token.client_id
