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

import httpx
import yaml
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
from oura_mcp_server.admin.log_buffer import InMemoryLogHandler
from oura_mcp_server.admin.templates import error_banner, page
from oura_mcp_server.auth import tenants as tenants_mod
from oura_mcp_server.auth.token_store import TokenStore
from oura_mcp_server.client.oura import OuraClient
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


def _html(body: str, *, status_code: int = 200) -> HTMLResponse:
    """Toda pagina de /admin va sin cachear.

    Alguna (la que revela una key recien creada) trae secretos en claro y no
    debe quedar en el cache de disco ni en el bfcache del navegador, donde
    reaparecería despues de que el servidor ya descarto el token de un solo uso.
    """
    return HTMLResponse(body, status_code=status_code, headers={"Cache-Control": "no-store"})


def _error_yaml(titulo: str, exc: Exception) -> HTMLResponse:
    """tenants.yaml roto o ilegible: el panel lo cuenta en la pagina.

    Es justo la pagina a la que el admin entra a diagnosticar el problema, asi
    que no puede ser un 500. El texto de la excepcion puede incluir trozos del
    YAML, por eso se escapa antes de meterlo en el HTML.
    """
    return _html(
        page(
            titulo,
            error_banner(
                f"Error leyendo/escribiendo tenants.yaml: {escape(str(exc), quote=True)}"
            ),
        )
    )


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

    # Un solo InMemoryLogHandler por servidor: si register_admin_routes se
    # vuelve a llamar (tests, o un reinicio del build), no queremos que se
    # acumulen handlers viejos en el logger compartido.
    target_logger = logging.getLogger("oura_mcp_server")
    for h in list(target_logger.handlers):
        if isinstance(h, InMemoryLogHandler):
            target_logger.removeHandler(h)
    log_buffer = InMemoryLogHandler()
    target_logger.addHandler(log_buffer)

    @mcp.custom_route("/admin/login", methods=["GET", "POST"])
    async def admin_login(request: Request) -> Response:
        next_path = _safe_next_path(request.query_params.get("next", "/admin/tenants"))

        if request.method == "GET":
            body = _FORMULARIO_LOGIN.format(next=escape(next_path, quote=True), error="")
            return _html(page("Entrar", body, show_nav=False))

        if not settings.admin_password:
            return _html(
                page("Entrar", error_banner("ADMIN_PASSWORD no esta configurado."), show_nav=False),
                status_code=500,
            )
        if not settings.oura_state_secret:
            return _html(
                page("Entrar", error_banner("OURA_STATE_SECRET no esta configurado."), show_nav=False),
                status_code=500,
            )
        if login_rate_limiter.bloqueado():
            return _html(
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

        # Se comparan bytes, no str: compare_digest sobre str exige ASCII puro y
        # lanza TypeError con un password con acentos (o con un ADMIN_PASSWORD
        # no-ASCII, que dejaria el panel inservible).
        if not secrets.compare_digest(
            password.encode("utf-8"), settings.admin_password.encode("utf-8")
        ):
            login_rate_limiter.registrar_fallo()
            body = _FORMULARIO_LOGIN.format(
                next=escape(next_target, quote=True), error=error_banner("Password incorrecta.")
            )
            return _html(page("Entrar", body, show_nav=False), status_code=401)

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

        try:
            entradas = tenants_store.list_all(Path(settings.tenants_config_path))
        except (yaml.YAMLError, OSError) as exc:
            return _error_yaml("Tenants", exc)
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
        return _html(page("Tenants", body))

    @mcp.custom_route("/admin/tenants/create", methods=["POST"])
    async def admin_tenants_create(request: Request) -> Response:
        guard = _require_admin(request, settings)
        if guard is not None:
            return guard

        form = await request.form()
        session_cookie = request.cookies.get(ADMIN_SESSION_COOKIE, "")
        if not is_valid_csrf_token(str(form.get("csrf") or ""), session_cookie, _admin_secret(settings)):
            return _html(page("Tenants", error_banner("CSRF invalido.")), status_code=403)

        tenant_id = str(form.get("tenant_id") or "").strip()
        tenant_name = str(form.get("tenant_name") or tenant_id).strip()
        user = str(form.get("user") or "").strip()
        agent = str(form.get("agent") or "").strip()
        if not tenant_id or not user:
            return _html(
                page("Tenants", error_banner("Tenant y user son obligatorios.")), status_code=400
            )

        try:
            key = tenants_store.create_key(
                Path(settings.tenants_config_path), tenant_id, tenant_name, agent, user
            )
        except (yaml.YAMLError, OSError) as exc:
            return _error_yaml("Tenants", exc)
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
            return _html(page("Tenants", error_banner("CSRF invalido.")), status_code=403)

        key_id = str(form.get("key_id") or "")
        try:
            tenants_store.revoke_key(Path(settings.tenants_config_path), key_id)
        except (yaml.YAMLError, OSError) as exc:
            return _error_yaml("Tenants", exc)
        tenants_mod.reload()
        return RedirectResponse("/admin/tenants", status_code=303)

    @mcp.custom_route("/admin/oauth", methods=["GET"])
    async def admin_oauth(request: Request) -> Response:
        guard = _require_admin(request, settings)
        if guard is not None:
            return guard

        csrf = create_csrf_token(request.cookies[ADMIN_SESSION_COOKIE], _admin_secret(settings))
        try:
            entradas = tenants_store.list_all(Path(settings.tenants_config_path))
        except (yaml.YAMLError, OSError) as exc:
            return _error_yaml("Conexiones OAuth", exc)
        registros = {r.user_id: r for r in store.list_with_metadata()}
        usuarios = sorted({e.user for e in entradas if e.user} | set(registros.keys()))

        filas = []
        for user_id in usuarios:
            keys_de_usuario = [e for e in entradas if e.user == user_id]
            tenant_desc = ", ".join(
                f"{escape(e.tenant_id, quote=True)}/{escape(e.agent, quote=True)}"
                for e in keys_de_usuario
            ) or "(sin key)"
            registro = registros.get(user_id)
            if registro is None:
                estado, scopes, actualizado, boton = "no conectado", "", "", ""
            else:
                expirado = "si" if registro.tokens.is_expired() else "no"
                estado = f"conectado (access token expirado ahora: {expirado})"
                scopes = escape(registro.tokens.scope or "", quote=True)
                actualizado = escape(registro.updated_at, quote=True)
                boton = (
                    "<form method='post' action='/admin/oauth/desconectar' style='margin:0'>"
                    f'<input type="hidden" name="csrf" value="{escape(csrf, quote=True)}">'
                    f"<input type='hidden' name='user_id' value='{escape(user_id, quote=True)}'>"
                    "<button type='submit'>Forzar reconexion</button></form>"
                )
            filas.append(
                f"<tr><td>{escape(user_id, quote=True)}</td><td>{tenant_desc}</td><td>{estado}</td>"
                f"<td>{scopes}</td><td>{actualizado}</td><td>{boton}</td></tr>"
            )

        body = f"""
<table>
<tr><th>Usuario</th><th>Tenant/agente</th><th>Estado</th><th>Scopes</th>
    <th>Actualizado</th><th></th></tr>
{"".join(filas)}
</table>
"""
        return _html(page("Conexiones OAuth", body))

    @mcp.custom_route("/admin/oauth/desconectar", methods=["POST"])
    async def admin_oauth_desconectar(request: Request) -> Response:
        guard = _require_admin(request, settings)
        if guard is not None:
            return guard

        form = await request.form()
        session_cookie = request.cookies.get(ADMIN_SESSION_COOKIE, "")
        if not is_valid_csrf_token(str(form.get("csrf") or ""), session_cookie, _admin_secret(settings)):
            return _html(page("Conexiones OAuth", error_banner("CSRF invalido.")), status_code=403)

        user_id = str(form.get("user_id") or "")
        if user_id:
            store.delete(user_id)
        return RedirectResponse("/admin/oauth", status_code=303)

    @mcp.custom_route("/admin/webhooks", methods=["GET"])
    async def admin_webhooks(request: Request) -> Response:
        guard = _require_admin(request, settings)
        if guard is not None:
            return guard

        csrf = create_csrf_token(request.cookies[ADMIN_SESSION_COOKIE], _admin_secret(settings))

        if not settings.oura_client_id or not settings.oura_client_secret:
            body = error_banner(
                "OURA_CLIENT_ID / OURA_CLIENT_SECRET no configurados: no se pueden "
                "gestionar webhooks."
            )
            return _html(page("Webhooks", body))

        client = OuraClient(settings, "")
        try:
            suscripciones = await client.list_webhooks()
        except httpx.HTTPStatusError as exc:
            body = error_banner(f"Error al listar webhooks: {exc.response.status_code}")
            return _html(page("Webhooks", body))

        def _fila_webhook(s: dict) -> str:
            wid = escape(str(s.get("id", "")), quote=True)
            callback = escape(str(s.get("callback_url", "")), quote=True)
            event_type = escape(str(s.get("event_type", "")), quote=True)
            data_type = escape(str(s.get("data_type", "")), quote=True)
            expiration = escape(str(s.get("expiration_time", "")), quote=True)
            return (
                f"<tr><td>{wid}</td><td>{callback}</td>"
                f"<td>{event_type}</td><td>{data_type}</td>"
                f"<td>{expiration}</td><td>"
                "<form method='post' action='/admin/webhooks/renovar' style='display:inline'>"
                f"<input type='hidden' name='csrf' value='{escape(csrf, quote=True)}'>"
                f"<input type='hidden' name='subscription_id' value='{wid}'>"
                "<button type='submit'>Renovar</button></form> "
                "<form method='post' action='/admin/webhooks/eliminar' style='display:inline'>"
                f"<input type='hidden' name='csrf' value='{escape(csrf, quote=True)}'>"
                f"<input type='hidden' name='subscription_id' value='{wid}'>"
                "<button type='submit'>Eliminar</button></form>"
                "</td></tr>"
            )

        filas = "".join(_fila_webhook(s) for s in suscripciones)

        callback_url = escape(f"https://{request.url.hostname}/webhooks/oura", quote=True)
        verification_token = escape(settings.oura_webhook_verification_token or "", quote=True)
        body = f"""
<table>
<tr><th>ID</th><th>Callback</th><th>Event</th><th>Data</th><th>Expira</th><th></th></tr>
{filas}
</table>
<h3>Crear suscripcion</h3>
<form method="post" action="/admin/webhooks/crear">
  <input type="hidden" name="csrf" value="{escape(csrf, quote=True)}">
  <label>Callback URL <input name="callback_url" value="{callback_url}" required></label><br>
  <label>Verification token
    <input name="verification_token" value="{verification_token}" required>
  </label><br>
  <label>Event type <input name="event_type" value="update"></label><br>
  <label>Data type <input name="data_type" value="daily_sleep"></label><br>
  <button type="submit">Crear</button>
</form>
"""
        return _html(page("Webhooks", body))

    @mcp.custom_route("/admin/webhooks/crear", methods=["POST"])
    async def admin_webhooks_crear(request: Request) -> Response:
        guard = _require_admin(request, settings)
        if guard is not None:
            return guard
        form = await request.form()
        session_cookie = request.cookies.get(ADMIN_SESSION_COOKIE, "")
        if not is_valid_csrf_token(str(form.get("csrf") or ""), session_cookie, _admin_secret(settings)):
            return _html(page("Webhooks", error_banner("CSRF invalido.")), status_code=403)

        client = OuraClient(settings, "")
        try:
            await client.create_webhook(
                callback_url=str(form.get("callback_url") or ""),
                verification_token=str(form.get("verification_token") or ""),
                event_type=str(form.get("event_type") or "update"),
                data_type=str(form.get("data_type") or "daily_sleep"),
            )
        except httpx.HTTPStatusError as exc:
            return _html(
                page("Webhooks", error_banner(f"Error al crear: {exc.response.status_code}")),
                status_code=502,
            )
        return RedirectResponse("/admin/webhooks", status_code=303)

    @mcp.custom_route("/admin/webhooks/renovar", methods=["POST"])
    async def admin_webhooks_renovar(request: Request) -> Response:
        guard = _require_admin(request, settings)
        if guard is not None:
            return guard
        form = await request.form()
        session_cookie = request.cookies.get(ADMIN_SESSION_COOKIE, "")
        if not is_valid_csrf_token(str(form.get("csrf") or ""), session_cookie, _admin_secret(settings)):
            return _html(page("Webhooks", error_banner("CSRF invalido.")), status_code=403)

        client = OuraClient(settings, "")
        try:
            await client.renew_webhook(str(form.get("subscription_id") or ""))
        except httpx.HTTPStatusError as exc:
            return _html(
                page("Webhooks", error_banner(f"Error al renovar: {exc.response.status_code}")),
                status_code=502,
            )
        return RedirectResponse("/admin/webhooks", status_code=303)

    @mcp.custom_route("/admin/webhooks/eliminar", methods=["POST"])
    async def admin_webhooks_eliminar(request: Request) -> Response:
        guard = _require_admin(request, settings)
        if guard is not None:
            return guard
        form = await request.form()
        session_cookie = request.cookies.get(ADMIN_SESSION_COOKIE, "")
        if not is_valid_csrf_token(str(form.get("csrf") or ""), session_cookie, _admin_secret(settings)):
            return _html(page("Webhooks", error_banner("CSRF invalido.")), status_code=403)

        client = OuraClient(settings, "")
        try:
            await client.delete_webhook(str(form.get("subscription_id") or ""))
        except httpx.HTTPStatusError as exc:
            return _html(
                page("Webhooks", error_banner(f"Error al eliminar: {exc.response.status_code}")),
                status_code=502,
            )
        return RedirectResponse("/admin/webhooks", status_code=303)

    @mcp.custom_route("/admin/health", methods=["GET"])
    async def admin_health(request: Request) -> Response:
        guard = _require_admin(request, settings)
        if guard is not None:
            return guard

        try:
            entradas = tenants_store.list_all(Path(settings.tenants_config_path))
        except (yaml.YAMLError, OSError) as exc:
            return _error_yaml("Salud", exc)
        conectados = store.list_user_ids()

        campos = {
            "OURA_CLIENT_ID": bool(settings.oura_client_id),
            "OURA_CLIENT_SECRET": bool(settings.oura_client_secret),
            "OURA_STATE_SECRET": bool(settings.oura_state_secret),
            "OURA_WEBHOOK_VERIFICATION_TOKEN": bool(settings.oura_webhook_verification_token),
            "TENANTS_CONFIG_PATH": settings.tenants_config_path,
        }
        filas_config = "".join(
            f"<tr><td>{escape(str(nombre), quote=True)}</td>"
            f"<td>{escape(str(valor), quote=True)}</td></tr>"
            for nombre, valor in campos.items()
        )
        filas_logs = "".join(
            f"<tr><td>{escape(e.level, quote=True)}</td>"
            f"<td>{escape(e.logger_name, quote=True)}</td>"
            f"<td>{escape(e.message, quote=True)}</td>"
            f"<td>{escape(e.created_at, quote=True)}</td></tr>"
            for e in log_buffer.entries()
        )

        body = f"""
<p>tenants/keys: {len(entradas)} · usuarios conectados: {len(conectados)}</p>
<table>
<tr><th>Config</th><th>Valor</th></tr>
{filas_config}
</table>
<h3>Avisos recientes</h3>
<table>
<tr><th>Nivel</th><th>Logger</th><th>Mensaje</th><th>Cuando</th></tr>
{filas_logs}
</table>
"""
        return _html(page("Salud", body))
