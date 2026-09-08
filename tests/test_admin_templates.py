from __future__ import annotations

from oura_mcp_server.admin.templates import error_banner, page


def test_page_incluye_el_titulo_y_el_cuerpo() -> None:
    html = page("Tenants", "<p>hola</p>")
    assert "<title>Tenants · Oura MCP admin</title>" in html
    assert "<h2>Tenants</h2>" in html
    assert "<p>hola</p>" in html


def test_page_incluye_la_navegacion_por_defecto() -> None:
    html = page("X", "")
    assert 'href="/admin/tenants"' in html
    assert 'href="/admin/logout"' in html


def test_page_puede_ocultar_la_navegacion() -> None:
    html = page("Login", "", show_nav=False)
    assert 'href="/admin/tenants"' not in html


def test_error_banner_envuelve_el_mensaje() -> None:
    assert error_banner("mal") == '<p class="error">mal</p>'
