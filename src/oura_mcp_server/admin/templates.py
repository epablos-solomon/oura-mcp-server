"""Helpers de HTML para el panel /admin.

Sin Jinja2: mismo estilo que core/web_routes.py (_FORMULARIO_LOGIN), strings
simples de Python porque hay un solo admin y cuatro paneles chicos.
"""
from __future__ import annotations

_NAV = """
<nav style="margin-bottom:1.5rem">
  <a href="/admin/tenants">Tenants</a> ·
  <a href="/admin/oauth">Conexiones OAuth</a> ·
  <a href="/admin/webhooks">Webhooks</a> ·
  <a href="/admin/health">Salud</a> ·
  <a href="/admin/logout">Salir</a>
</nav>
"""


def page(title: str, body_html: str, *, show_nav: bool = True) -> str:
    nav = _NAV if show_nav else ""
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} · Oura MCP admin</title>
<style>
  body {{ font-family: sans-serif; max-width: 60rem; margin: 2rem auto; padding: 0 1rem; }}
  table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
  th, td {{ border: 1px solid #ccc; padding: .4rem .6rem; text-align: left; }}
  .error {{ color: #b00020; }}
  .aviso {{ background: #fff3cd; padding: .6rem; border-radius: 4px; }}
</style>
</head>
<body>
{nav}
<h2>{title}</h2>
{body_html}
</body></html>"""


def error_banner(mensaje: str) -> str:
    return f'<p class="error">{mensaje}</p>'
