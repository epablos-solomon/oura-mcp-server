"""Rutas HTTP auxiliares montadas en el mismo servidor FastMCP.

Conviven con el endpoint MCP (`/mcp`) en el mismo puerto:
- GET  /health            -> healthcheck
- GET  /auth/login?key=   -> inicia OAuth para la persona identificada por su API key
- GET  /auth/callback     -> intercambia el code y guarda tokens del usuario correcto
- GET/POST /webhooks/oura -> verificacion + recepcion de eventos de Oura
"""
from __future__ import annotations

import logging

from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse

from oura_mcp_server.auth.oauth import OuraOAuth2Manager
from oura_mcp_server.auth.state import sign_state, verify_state
from oura_mcp_server.auth.tenants import resolve_tenant
from oura_mcp_server.auth.token_store import TokenStore
from oura_mcp_server.config import Settings

logger = logging.getLogger(__name__)


def register_web_routes(mcp, settings: Settings, store: TokenStore) -> None:
    oauth = OuraOAuth2Manager(settings)

    @mcp.custom_route("/health", methods=["GET"])
    async def health(_request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "service": settings.app_name})

    @mcp.custom_route("/auth/login", methods=["GET"])
    async def auth_login(request: Request):
        if not settings.oura_client_id:
            return JSONResponse({"error": "OURA_CLIENT_ID not configured"}, status_code=400)
        if not settings.oura_state_secret:
            return JSONResponse({"error": "OURA_STATE_SECRET not configured"}, status_code=500)

        api_key = request.query_params.get("key")
        if not api_key:
            return JSONResponse(
                {"error": "Falta ?key=<tu-api-key>. Usa tu link personalizado."},
                status_code=400,
            )
        tenant = resolve_tenant(api_key)
        if tenant is None:
            return JSONResponse({"error": "API key invalida"}, status_code=401)

        state = sign_state(tenant.oura_user_id, settings.oura_state_secret)
        return RedirectResponse(oauth.get_authorization_url(state))

    @mcp.custom_route("/auth/callback", methods=["GET"])
    async def auth_callback(request: Request):
        code = request.query_params.get("code")
        state = request.query_params.get("state")
        if not code or not state:
            return JSONResponse({"error": "Missing code or state"}, status_code=400)
        if not settings.oura_state_secret:
            return JSONResponse({"error": "OURA_STATE_SECRET not configured"}, status_code=500)

        user_id = verify_state(state, settings.oura_state_secret)
        if user_id is None:
            return JSONResponse({"error": "state invalido o expirado"}, status_code=400)

        tokens = await oauth.exchange_code(code)
        store.save(user_id, tokens)
        logger.info("Oura conectado para user_id=%s", user_id)
        return HTMLResponse(
            f"<html><body style='font-family:sans-serif'>"
            f"<h2>Cuenta Oura conectada</h2>"
            f"<p>Listo, <b>{user_id}</b>. Ya puedes cerrar esta pestana.</p>"
            f"</body></html>"
        )

    @mcp.custom_route("/webhooks/oura", methods=["GET", "POST"])
    async def oura_webhook(request: Request) -> JSONResponse:
        # Oura verifica la suscripcion con un GET ?verification_token=&challenge=
        if request.method == "GET":
            challenge = request.query_params.get("challenge")
            return JSONResponse({"challenge": challenge})
        payload = await request.json()
        logger.info(
            "Webhook Oura: %s/%s", payload.get("event_type"), payload.get("data_type")
        )
        return JSONResponse({"status": "received"})
