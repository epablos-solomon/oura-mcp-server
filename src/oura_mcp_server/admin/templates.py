"""Helpers de HTML para el panel /admin.

Sin Jinja2: mismo estilo que core/web_routes.py (_FORMULARIO_LOGIN), strings
simples de Python porque hay un solo admin y cuatro paneles chicos. El CSS
vive inline en page() a proposito, por la misma razon: no hay build step ni
archivos estaticos que servir, todo el panel es un solo proceso Python.
"""
from __future__ import annotations

import base64
from pathlib import Path

from oura_mcp_server.admin.webhook_options import (
    WEBHOOK_DATA_TYPES,
    WEBHOOK_EVENT_TYPES,
    select_options,
)

_LOGO_PATH = Path(__file__).parent / "assets" / "logo.png"


def _logo_data_uri() -> str:
    try:
        data = base64.b64encode(_LOGO_PATH.read_bytes()).decode("ascii")
    except OSError:
        return ""
    return f"data:image/png;base64,{data}"


_LOGO_DATA_URI = _logo_data_uri()

_NAV_LINKS = [
    ("/admin/tenants", "Tenants"),
    ("/admin/oauth", "Conexiones OAuth"),
    ("/admin/webhooks", "Webhooks"),
    ("/admin/health", "Salud"),
]

_LOGO_IMG = f'<img src="{_LOGO_DATA_URI}" alt="Scaleflow" class="logo">' if _LOGO_DATA_URI else ""

_NAV = f"""
<header class="topbar">
  <a href="/admin/tenants" class="brand">{_LOGO_IMG}</a>
  <nav>
    {"".join(f'<a href="{href}">{label}</a>' for href, label in _NAV_LINKS)}
    <a href="/admin/logout" class="nav-exit">Salir</a>
  </nav>
</header>
"""

_LOGO_ONLY = f'<header class="topbar topbar-plain">{_LOGO_IMG}</header>' if _LOGO_IMG else ""

_STYLE = """
:root {
  --bg: #f7f7fb;
  --surface: #ffffff;
  --ink: #1d1b31;
  --muted: #6b6580;
  --line: #e6e4f0;
  --brand-start: #7c3aed;
  --brand-end: #4f46e5;
  --danger: #dc2626;
  --danger-bg: #fef2f2;
  --success: #059669;
  --success-bg: #ecfdf5;
  --radius: 10px;
  --radius-sm: 8px;
}
* { box-sizing: border-box; }
body {
  font-family: ui-rounded, "SF Pro Rounded", "Segoe UI", system-ui, -apple-system, sans-serif;
  background: var(--bg);
  color: var(--ink);
  margin: 0;
  padding: 0 0 3rem;
}
body::before {
  content: "";
  display: block;
  height: 3px;
  background: linear-gradient(90deg, var(--brand-start), var(--brand-end));
}
.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  max-width: 60rem;
  margin: 0 auto;
  padding: 1.1rem 1.5rem;
  border-bottom: 1px solid var(--line);
}
.brand { display: flex; align-items: center; }
.logo { height: 26px; display: block; }
.topbar nav { display: flex; align-items: center; gap: 1.4rem; font-size: .92rem; }
.topbar nav a { color: var(--muted); text-decoration: none; }
.topbar nav a:hover, .topbar nav a:focus-visible { color: var(--ink); }
.nav-exit { color: var(--brand-end) !important; }
.topbar-plain { justify-content: center; border-bottom: none; padding-top: 2.5rem; }
.login-card { max-width: 22rem; margin: 1.5rem auto 0; text-align: left; }
.main-narrow { text-align: center; }
.main-narrow h2 { color: var(--muted); font-size: 1rem; font-weight: 500; }
main {
  max-width: 60rem;
  margin: 0 auto;
  padding: 2rem 1.5rem 0;
}
h2 { font-size: 1.4rem; margin: 0; letter-spacing: -0.01em; }
.page-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  margin: 0 0 1.25rem;
}
.main-narrow .page-title { justify-content: center; }
h3 { font-size: 1.05rem; margin: 2rem 0 .75rem; }
.card {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 1.25rem 1.5rem;
  margin-bottom: 1.5rem;
}
table { border-collapse: collapse; width: 100%; }
th, td { padding: .6rem .5rem; text-align: left; border-bottom: 1px solid var(--line); }
th { font-size: .78rem; text-transform: none; color: var(--muted); font-weight: 600; }
tr:last-child td { border-bottom: none; }
code {
  font-family: ui-monospace, "SF Mono", Menlo, monospace;
  background: var(--bg);
  border: 1px solid var(--line);
  border-radius: 4px;
  padding: .1rem .35rem;
  font-size: .85rem;
}
label { display: block; font-size: .85rem; color: var(--muted); margin: .85rem 0 .3rem; }
input, select {
  width: 100%;
  padding: .55rem .7rem;
  border: 1px solid var(--line);
  border-radius: var(--radius-sm);
  font-size: .95rem;
  font-family: inherit;
  background: var(--surface);
  color: var(--ink);
}
input:focus-visible, select:focus-visible { outline: 2px solid var(--brand-end); outline-offset: 1px; }
button {
  font-family: inherit;
  font-size: .9rem;
  font-weight: 600;
  padding: .55rem 1.1rem;
  border-radius: var(--radius-sm);
  border: 1px solid transparent;
  cursor: pointer;
}
button[type="submit"], .btn-primary {
  background: linear-gradient(135deg, var(--brand-start), var(--brand-end));
  color: #fff;
}
button[type="submit"]:hover { filter: brightness(1.06); }
.btn-danger {
  background: var(--danger-bg);
  border-color: #fecaca;
  color: var(--danger);
}
.badge {
  display: inline-block;
  padding: .15rem .55rem;
  border-radius: 999px;
  font-size: .78rem;
  font-weight: 600;
}
.badge-ok { background: var(--success-bg); color: var(--success); }
.badge-off { background: var(--line); color: var(--muted); }
.error { color: var(--danger); }
.aviso {
  background: var(--success-bg);
  border: 1px solid #a7f3d0;
  border-radius: var(--radius);
  padding: 1rem 1.25rem;
  margin-bottom: 1.5rem;
}
.key-copy { display: flex; gap: .5rem; margin-top: .75rem; }
.key-copy input { font-family: ui-monospace, "SF Mono", Menlo, monospace; font-size: .9rem; }
.key-copy button { flex-shrink: 0; }
.key-cell { display: flex; align-items: center; gap: .45rem; flex-wrap: wrap; }
.key-cell form { margin: 0; }
button.btn-quiet {
  background: transparent;
  border-color: var(--line);
  color: var(--brand-end);
  padding: .28rem .7rem;
  font-size: .8rem;
  font-weight: 600;
}
button.btn-quiet:hover { background: var(--bg); }
.key-dialog {
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 0;
  width: min(32rem, calc(100% - 2rem));
  box-shadow: 0 18px 50px rgba(29, 27, 49, .18);
}
.key-dialog::backdrop { background: rgba(29, 27, 49, .45); }
.key-dialog-inner { padding: 1.5rem 1.6rem 1.35rem; }
.key-dialog h3 { margin: 0 0 .35rem; }
.key-dialog p.hint { color: var(--muted); font-size: .9rem; margin: 0; }
.key-dialog .key-copy input {
  letter-spacing: .01em;
  padding: .7rem .8rem;
  background: var(--bg);
}
.key-dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: .5rem;
  margin: 1.1rem 0 0;
}
.key-dialog-actions p { margin: 0; }
@media (prefers-reduced-motion: reduce) {
  .key-dialog { animation: none; }
}
"""


def page(
    title: str, body_html: str, *, show_nav: bool = True, heading_actions: str = ""
) -> str:
    nav = _NAV if show_nav else _LOGO_ONLY
    main_class = "" if show_nav else ' class="main-narrow"'
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} · Oura MCP admin</title>
<style>{_STYLE}</style>
</head>
<body>
{nav}
<main{main_class}>
<div class="page-title"><h2>{title}</h2>{heading_actions}</div>
{body_html}
</main>
</body></html>"""


def error_banner(mensaje: str) -> str:
    return f'<p class="error">{mensaje}</p>'


def key_reveal_dialog(key: str) -> str:
    """Dialogo modal con la key en claro y boton Copiar.

    La key llega ya escapada para HTML (el caller usa html.escape). El
    <script> llama a showModal() para el backdrop nativo; al cerrar limpia
    ?reveal= de la URL para que un refresh no intente reusar el token.
    """
    return f"""
<dialog id="key-dialog" class="key-dialog">
  <div class="key-dialog-inner">
    <h3>API key</h3>
    <p class="hint">Cópiala ahora. En la tabla solo se ve enmascarada.</p>
    <div class="key-copy">
      <input type="text" id="key-value" value="{key}" readonly>
      <button type="button" id="copy-btn" class="btn-primary">Copiar</button>
    </div>
    <form method="dialog" class="key-dialog-actions">
      <button type="submit" class="btn-quiet">Hecho</button>
    </form>
  </div>
</dialog>
<script>
(function() {{
  var d = document.getElementById("key-dialog");
  var btn = document.getElementById("copy-btn");
  var input = document.getElementById("key-value");
  if (d && d.showModal) d.showModal();
  if (input) input.addEventListener("focus", function() {{ input.select(); }});
  if (btn && input) {{
    btn.addEventListener("click", function() {{
      var done = function() {{
        btn.textContent = "¡Copiado!";
        setTimeout(function() {{ btn.textContent = "Copiar"; }}, 1500);
      }};
      var fallback = function() {{
        input.focus();
        input.select();
        try {{ if (document.execCommand("copy")) done(); }} catch (e) {{}}
      }};
      if (navigator.clipboard && navigator.clipboard.writeText) {{
        navigator.clipboard.writeText(input.value).then(done).catch(fallback);
      }} else {{
        fallback();
      }}
    }});
  }}
  if (d) {{
    d.addEventListener("close", function() {{
      if (location.search.indexOf("reveal=") !== -1) {{
        history.replaceState(null, "", "/admin/tenants");
      }}
    }});
  }}
}})();
</script>
"""


def create_key_form_dialog(csrf: str) -> str:
    """Formulario de alta dentro de un <dialog>, no en la pagina.

    csrf llega ya escapado. El boton de la cabecera (#open-create-dialog)
    vive fuera de este HTML: page(heading_actions=...).
    """
    return f"""
<dialog id="create-dialog" class="key-dialog">
  <div class="key-dialog-inner">
    <h3>Crear key nueva</h3>
    <form method="post" action="/admin/tenants/create">
      <input type="hidden" name="csrf" value="{csrf}">
      <label>Tenant</label><input name="tenant_id" value="scaleflow" required>
      <label>Tenant name</label><input name="tenant_name" value="Scaleflow Internal" required>
      <label>User</label><input name="user" required>
      <label>Agent</label><input name="agent" required>
      <div class="key-dialog-actions">
        <button type="button" class="btn-quiet" id="close-create-dialog">Cancelar</button>
        <button type="submit">Crear</button>
      </div>
    </form>
  </div>
</dialog>
<script>
(function() {{
  var d = document.getElementById("create-dialog");
  var openBtn = document.getElementById("open-create-dialog");
  var closeBtn = document.getElementById("close-create-dialog");
  if (openBtn && d && d.showModal) {{
    openBtn.addEventListener("click", function() {{
      d.showModal();
      var user = d.querySelector("input[name=user]");
      if (user) user.focus();
    }});
  }}
  if (closeBtn && d) closeBtn.addEventListener("click", function() {{ d.close(); }});
}})();
</script>
"""


def create_webhook_form_dialog(csrf: str, callback_url: str, verification_token: str) -> str:
    """Alta de suscripcion Oura en un <dialog>, con selects de enums oficiales.

    csrf, callback_url y verification_token llegan ya escapados para atributos.
    """
    event_opts = select_options(WEBHOOK_EVENT_TYPES, "update")
    data_opts = select_options(WEBHOOK_DATA_TYPES, "daily_sleep")
    return f"""
<dialog id="webhook-dialog" class="key-dialog">
  <div class="key-dialog-inner">
    <h3>Crear suscripción</h3>
    <form method="post" action="/admin/webhooks/crear">
      <input type="hidden" name="csrf" value="{csrf}">
      <label>Callback URL</label>
      <input name="callback_url" value="{callback_url}" required>
      <label>Verification token</label>
      <input name="verification_token" value="{verification_token}" required>
      <label>Event type</label>
      <select name="event_type" required>{event_opts}</select>
      <label>Data type</label>
      <select name="data_type" required>{data_opts}</select>
      <div class="key-dialog-actions">
        <button type="button" class="btn-quiet" id="close-webhook-dialog">Cancelar</button>
        <button type="submit">Crear</button>
      </div>
    </form>
  </div>
</dialog>
<script>
(function() {{
  var d = document.getElementById("webhook-dialog");
  var openBtn = document.getElementById("open-webhook-dialog");
  var closeBtn = document.getElementById("close-webhook-dialog");
  if (openBtn && d && d.showModal) {{
    openBtn.addEventListener("click", function() {{ d.showModal(); }});
  }}
  if (closeBtn && d) closeBtn.addEventListener("click", function() {{ d.close(); }});
}})();
</script>
"""
