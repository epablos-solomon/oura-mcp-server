"""Rutas del panel de administracion (/admin/*).

Vive en el mismo proceso FastMCP/Starlette que /mcp y /auth/* (ver
core/web_routes.py): un solo admin, sin trafico, no justifica un servicio
aparte. HTML generado en Python (admin/templates.py), sin Jinja2.
"""
from __future__ import annotations

import logging
import secrets

from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response

from oura_mcp_server.admin.auth import (
    ADMIN_SESSION_COOKIE,
    LoginRateLimiter,
    create_admin_session,
    is_valid_admin_session,
)
from oura_mcp_server.admin.templates import error_banner, page
from oura_mcp_server.auth.token_store import TokenStore
from oura_mcp_server.config import Settings

logger = logging.getLogger(__name__)

_FORMULARIO_LOGIN = """
<form method="post" action="/admin/login">
  <input type="hidden" name="next" value="{next}">
  <input type="password" name="password" placeholder="Password de admin"
         autocomplete="off" required style="width:100%;padding:.6rem;font-size:1rem">
  <button type="submit" style="margin-top:.8rem;padding:.6rem 1.2rem;font-size:1rem">
    Entrar
  </button>
</form>
{error}
"""


def _admin_secret(settings: Settings) -> str:
    return settings.oura_state_secret or ""


def _require_admin(request: Request, settings: Settings) -> RedirectResponse | None:
    cookie = request.cookies.get(ADMIN_SESSION_COOKIE)
    if is_valid_admin_session(cookie, _admin_secret(settings)):
        return None
    next_path = request.url.path
    return RedirectResponse(f"/admin/login?next={next_path}", status_code=302)


def register_admin_routes(mcp, settings: Settings, store: TokenStore) -> None:
    # Estado por-instancia: cada llamada a register_admin_routes (un servidor
    # nuevo, o un test nuevo) arranca con su propio rate limiter.
    login_rate_limiter = LoginRateLimiter()

    @mcp.custom_route("/admin/login", methods=["GET", "POST"])
    async def admin_login(request: Request) -> Response:
        next_path = request.query_params.get("next", "/admin/tenants")

        if request.method == "GET":
            body = _FORMULARIO_LOGIN.format(next=next_path, error="")
            return HTMLResponse(
                page("Entrar", body, show_nav=False), headers={"Cache-Control": "no-store"}
            )

        if not settings.admin_password:
            return HTMLResponse(
                page("Entrar", error_banner("ADMIN_PASSWORD no esta configurado."), show_nav=False),
                status_code=500,
            )
        if not settings.oura_state_secret:
            return HTMLResponse(
                page("Entrar", error_banner("OURA_STATE_SECRET no esta configurado."), show_nav=False),
                status_code=500,
            )
        if login_rate_limiter.bloqueado():
            return HTMLResponse(
                page(
                    "Entrar",
                    error_banner("Demasiados intentos fallidos. Espera unos minutos."),
                    show_nav=False,
                ),
                status_code=429,
            )

        form = await request.form()
        password = str(form.get("password") or "")
        next_target = str(form.get("next") or "/admin/tenants")

        if not secrets.compare_digest(password, settings.admin_password):
            login_rate_limiter.registrar_fallo()
            body = _FORMULARIO_LOGIN.format(
                next=next_target, error=error_banner("Password incorrecta.")
            )
            return HTMLResponse(page("Entrar", body, show_nav=False), status_code=401)

        login_rate_limiter.registrar_exito()
        session_cookie = create_admin_session(_admin_secret(settings))
        response = RedirectResponse(next_target, status_code=303)
        response.set_cookie(
            ADMIN_SESSION_COOKIE,
            session_cookie,
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=12 * 60 * 60,
        )
        return response

    @mcp.custom_route("/admin/logout", methods=["GET"])
    async def admin_logout(_request: Request) -> Response:
        response = RedirectResponse("/admin/login", status_code=302)
        response.delete_cookie(ADMIN_SESSION_COOKIE)
        return response
