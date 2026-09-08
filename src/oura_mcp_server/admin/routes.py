"""Rutas del panel de administracion (/admin/*).

Vive en el mismo proceso FastMCP/Starlette que /mcp y /auth/* (ver
core/web_routes.py): un solo admin, sin trafico, no justifica un servicio
aparte. HTML generado en Python (admin/templates.py), sin Jinja2.
"""
from __future__ import annotations

import logging
import secrets
from html import escape
from pathlib import Path

from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response

from oura_mcp_server.admin import tenants_store
from oura_mcp_server.admin.auth import (
    ADMIN_SESSION_COOKIE,
    LoginRateLimiter,
    create_admin_session,
    create_csrf_token,
    is_valid_admin_session,
    is_valid_csrf_token,
)
from oura_mcp_server.admin.templates import error_banner, page
from oura_mcp_server.auth import tenants as tenants_mod
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


def _safe_next_path(value: str) -> str:
    """Evita open-redirect: solo se acepta una ruta relativa de un solo `/`.

    `//evil.example` y `/\\evil.example` son ambiguos para algunos navegadores
    (los tratan como protocol-relative), asi que tambien se rechazan.
    """
    if value.startswith("/") and not value.startswith("//") and not value.startswith("/\\"):
        return value
    return "/admin/tenants"


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

    # token de un solo uso -> key completa recien creada; se muestra una vez
    # y se descarta al leerla (nunca viaja la key real en la URL).
    pending_key_reveals: dict[str, str] = {}

    @mcp.custom_route("/admin/login", methods=["GET", "POST"])
    async def admin_login(request: Request) -> Response:
        next_path = _safe_next_path(request.query_params.get("next", "/admin/tenants"))

        if request.method == "GET":
            body = _FORMULARIO_LOGIN.format(next=escape(next_path, quote=True), error="")
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
        next_target = _safe_next_path(str(form.get("next") or "/admin/tenants"))

        if not secrets.compare_digest(password, settings.admin_password):
            login_rate_limiter.registrar_fallo()
            body = _FORMULARIO_LOGIN.format(
                next=escape(next_target, quote=True), error=error_banner("Password incorrecta.")
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

    @mcp.custom_route("/admin/tenants", methods=["GET"])
    async def admin_tenants(request: Request) -> Response:
        guard = _require_admin(request, settings)
        if guard is not None:
            return guard

        csrf = create_csrf_token(request.cookies[ADMIN_SESSION_COOKIE], _admin_secret(settings))
        reveal_token = request.query_params.get("reveal", "")
        key_nueva = pending_key_reveals.pop(reveal_token, "") if reveal_token else ""

        entradas = tenants_store.list_all(Path(settings.tenants_config_path))
        filas = "".join(
            f"<tr><td>{escape(e.tenant_id, quote=True)}</td>"
            f"<td>{escape(e.user, quote=True)}</td>"
            f"<td>{escape(e.agent, quote=True)}</td>"
            f"<td><code>{escape(e.key_masked, quote=True)}</code></td>"
            f"<td><form method='post' action='/admin/tenants/revoke' style='margin:0'>"
            f"<input type='hidden' name='csrf' value='{escape(csrf, quote=True)}'>"
            f"<input type='hidden' name='key_id' value='{escape(e.key_id, quote=True)}'>"
            f"<button type='submit'>Revocar</button></form></td></tr>"
            for e in entradas
        )
        aviso = ""
        if key_nueva:
            aviso = (
                '<div class="aviso"><b>Key creada, copiala ahora — no se vuelve a mostrar:</b>'
                f"<pre>{escape(key_nueva, quote=True)}</pre></div>"
            )
        body = f"""
{aviso}
<table>
<tr><th>Tenant</th><th>User</th><th>Agent</th><th>Key</th><th></th></tr>
{filas}
</table>
<h3>Crear key nueva</h3>
<form method="post" action="/admin/tenants/create">
  <input type="hidden" name="csrf" value="{escape(csrf, quote=True)}">
  <label>Tenant <input name="tenant_id" value="scaleflow" required></label><br>
  <label>Tenant name <input name="tenant_name" value="Scaleflow Internal" required></label><br>
  <label>User <input name="user" required></label><br>
  <label>Agent <input name="agent" required></label><br>
  <button type="submit">Crear</button>
</form>
"""
        return HTMLResponse(page("Tenants", body))

    @mcp.custom_route("/admin/tenants/create", methods=["POST"])
    async def admin_tenants_create(request: Request) -> Response:
        guard = _require_admin(request, settings)
        if guard is not None:
            return guard

        form = await request.form()
        session_cookie = request.cookies.get(ADMIN_SESSION_COOKIE, "")
        if not is_valid_csrf_token(str(form.get("csrf") or ""), session_cookie, _admin_secret(settings)):
            return HTMLResponse(page("Tenants", error_banner("CSRF invalido.")), status_code=403)

        tenant_id = str(form.get("tenant_id") or "").strip()
        tenant_name = str(form.get("tenant_name") or tenant_id).strip()
        user = str(form.get("user") or "").strip()
        agent = str(form.get("agent") or "").strip()
        if not tenant_id or not user:
            return HTMLResponse(
                page("Tenants", error_banner("Tenant y user son obligatorios.")), status_code=400
            )

        key = tenants_store.create_key(
            Path(settings.tenants_config_path), tenant_id, tenant_name, agent, user
        )
        tenants_mod.reload()

        reveal_token = secrets.token_urlsafe(16)
        pending_key_reveals[reveal_token] = key
        return RedirectResponse(f"/admin/tenants?reveal={reveal_token}", status_code=303)

    @mcp.custom_route("/admin/tenants/revoke", methods=["POST"])
    async def admin_tenants_revoke(request: Request) -> Response:
        guard = _require_admin(request, settings)
        if guard is not None:
            return guard

        form = await request.form()
        session_cookie = request.cookies.get(ADMIN_SESSION_COOKIE, "")
        if not is_valid_csrf_token(str(form.get("csrf") or ""), session_cookie, _admin_secret(settings)):
            return HTMLResponse(page("Tenants", error_banner("CSRF invalido.")), status_code=403)

        key_id = str(form.get("key_id") or "")
        tenants_store.revoke_key(Path(settings.tenants_config_path), key_id)
        tenants_mod.reload()
        return RedirectResponse("/admin/tenants", status_code=303)
