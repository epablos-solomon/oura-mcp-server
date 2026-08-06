"""Rutas HTTP auxiliares montadas en el mismo servidor FastMCP.

Conviven con el endpoint MCP (`/mcp`) en el mismo puerto:
- GET  /health            -> healthcheck
- GET  /auth/login        -> formulario donde la persona pega su API key
- POST /auth/login        -> valida la key (en el cuerpo) e inicia OAuth
- GET  /auth/callback     -> intercambia el code y guarda tokens del usuario correcto
- GET/POST /webhooks/oura -> verificacion + recepcion de eventos de Oura
"""
from __future__ import annotations

import hmac
import logging

from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse

from oura_mcp_server.auth.oauth import OuraOAuth2Manager
from oura_mcp_server.auth.state import sign_state, verify_state
from oura_mcp_server.auth.tenants import resolve_tenant
from oura_mcp_server.auth.token_store import TokenStore
from oura_mcp_server.config import Settings

logger = logging.getLogger(__name__)

# La API key viaja en el cuerpo del POST: en la query string quedaria escrita en
# los logs de acceso del proxy y en el historial del navegador.
_FORMULARIO_LOGIN = """<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Conectar Oura</title></head>
<body style="font-family:sans-serif;max-width:26rem;margin:4rem auto;padding:0 1rem">
  <h2>Conectar tu cuenta Oura</h2>
  <p>Pega la API key que te dieron para este servidor.</p>
  <form method="post" action="/auth/login">
    <input type="password" name="key" placeholder="sk-..." autocomplete="off"
           required style="width:100%;padding:.6rem;font-size:1rem">
    <button type="submit" style="margin-top:.8rem;padding:.6rem 1.2rem;font-size:1rem">
      Continuar
    </button>
  </form>
</body></html>"""


def register_web_routes(mcp, settings: Settings, store: TokenStore) -> None:
    oauth = OuraOAuth2Manager(settings)

    @mcp.custom_route("/health", methods=["GET"])
    async def health(_request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "service": settings.app_name})

    @mcp.custom_route("/auth/login", methods=["GET", "POST"])
    async def auth_login(request: Request):
        if request.method == "GET":
            return HTMLResponse(_FORMULARIO_LOGIN, headers={"Cache-Control": "no-store"})

        if not settings.oura_client_id:
            return JSONResponse({"error": "OURA_CLIENT_ID not configured"}, status_code=400)
        if not settings.oura_state_secret:
            return JSONResponse({"error": "OURA_STATE_SECRET not configured"}, status_code=500)

        form = await request.form()
        api_key = str(form.get("key") or "").strip()
        if not api_key:
            return JSONResponse({"error": "Falta la API key."}, status_code=400)
        tenant = resolve_tenant(api_key)
        if tenant is None:
            return JSONResponse({"error": "API key invalida"}, status_code=401)

        state = sign_state(tenant.oura_user_id, settings.oura_state_secret)
        # 303: convierte el POST en un GET hacia Oura.
        return RedirectResponse(oauth.get_authorization_url(state), status_code=303)

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
        esperado = settings.oura_webhook_verification_token
        if not esperado:
            # Sin token configurado no hay forma de saber quien llama: falla
            # cerrado en vez de devolver el challenge a cualquiera.
            return JSONResponse(
                {"error": "webhook sin OURA_WEBHOOK_VERIFICATION_TOKEN configurado"},
                status_code=503,
            )
        recibido = request.query_params.get("verification_token", "")
        if not hmac.compare_digest(recibido, esperado):
            logger.warning("Webhook Oura rechazado: verification_token invalido")
            return JSONResponse({"error": "verification_token invalido"}, status_code=401)

        # Oura verifica la suscripcion con un GET ?verification_token=&challenge=
        if request.method == "GET":
            return JSONResponse({"challenge": request.query_params.get("challenge")})

        # POST: solo se registra el evento. No esta confirmado como autentica
        # Oura los POST de eventos, asi que este handler no debe adquirir
        # efectos de estado mientras no se verifique contra su documentacion.
        payload = await request.json()
        logger.info(
            "Webhook Oura: %s/%s", payload.get("event_type"), payload.get("data_type")
        )
        return JSONResponse({"status": "received"})
