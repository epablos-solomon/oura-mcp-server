"""Bearer API-key auth provider for the HTTP transport.

Same design as the memory MCP: extends `TokenVerifier` (simple bearer-token
auth) instead of the full OAuth `AuthProvider`, so plain API keys are accepted.
FastMCP calls `verify_token()` once per request.
"""
from __future__ import annotations

from fastmcp.server.auth import AccessToken, TokenVerifier

from oura_mcp_server.auth.tenants import resolve_tenant


class ApiKeyAuthProvider(TokenVerifier):
    async def verify_token(self, token: str) -> AccessToken | None:
        tenant = resolve_tenant(token)
        if tenant is None:
            return None
        return AccessToken(
            token=token,
            client_id=tenant.tenant_id,
            scopes=[],
            claims={
                "tenant_id": tenant.tenant_id,
                "agent": tenant.agent,
                "user": tenant.user,
                "oura_user_id": tenant.oura_user_id,
            },
        )
