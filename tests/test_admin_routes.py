"""Panel de administracion (/admin/*): login, tenants, OAuth, webhooks, salud."""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from oura_mcp_server.admin.auth import ADMIN_SESSION_COOKIE
from oura_mcp_server.admin.routes import register_admin_routes
from oura_mcp_server.auth import tenants as tenants_mod
from oura_mcp_server.auth.token_store import TokenStore
from oura_mcp_server.config import Settings
from oura_mcp_server.core.server import create_mcp_server

TENANTS_YAML = """
default_tenant: scaleflow
tenants:
  scaleflow:
    name: Scaleflow Internal
    api_keys:
      - key: sk-oura-kike-existente
        agent: claude-code
        user: kike
"""
ADMIN_PASSWORD = "correcto-caballo-bateria-grapadora"


@pytest.fixture
def cliente(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    (tmp_path / "tenants.yaml").write_text(TENANTS_YAML)
    settings = Settings(
        token_db_path=tmp_path / "t.sqlite3",
        oura_state_secret="secreto-de-test",
        oura_client_id="cid",
        oura_client_secret="csec",
        tenants_config_path=str(tmp_path / "tenants.yaml"),
        admin_password=ADMIN_PASSWORD,
    )
    # tenants.py lee la config por get_settings(), no por el objeto que se pasa
    # (mismo patron que tests/test_web_routes.py).
    monkeypatch.setattr(tenants_mod, "get_settings", lambda: settings)
    tenants_mod.reload()

    store = TokenStore(settings.token_db_path)
    mcp = create_mcp_server(settings, store)
    register_admin_routes(mcp, settings, store)

    # secure=True en la cookie de admin exige https: TestClient usa
    # http://testserver por defecto y httpx descarta cookies Secure ahi.
    test_client = TestClient(mcp.http_app(), base_url="https://testserver")
    test_client.store = store
    test_client.settings = settings
    yield test_client

    tenants_mod._key_lookup = None
    tenants_mod._default_tenant = None


def _login(cliente: TestClient) -> None:
    r = cliente.post(
        "/admin/login", data={"password": ADMIN_PASSWORD, "next": "/admin/tenants"},
        follow_redirects=False,
    )
    assert r.status_code == 303


def _csrf_de(cliente: TestClient, path: str = "/admin/tenants") -> str:
    pagina = cliente.get(path)
    match = re.search(r'name="csrf" value="([^"]+)"', pagina.text)
    assert match, f"no se encontro token csrf en {path}"
    return match.group(1)


# --- Login / logout ---

def test_get_login_muestra_el_formulario(cliente: TestClient) -> None:
    r = cliente.get("/admin/login")
    assert r.status_code == 200
    assert 'name="password"' in r.text


def test_post_login_con_password_correcta_setea_cookie_y_redirige(cliente: TestClient) -> None:
    r = cliente.post(
        "/admin/login", data={"password": ADMIN_PASSWORD, "next": "/admin/tenants"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"] == "/admin/tenants"
    assert ADMIN_SESSION_COOKIE in r.cookies


def test_post_login_con_password_incorrecta_rechaza(cliente: TestClient) -> None:
    r = cliente.post(
        "/admin/login", data={"password": "mala", "next": "/admin/tenants"},
        follow_redirects=False,
    )
    assert r.status_code == 401
    assert ADMIN_SESSION_COOKIE not in r.cookies


def test_tras_varios_fallos_el_login_se_bloquea(cliente: TestClient) -> None:
    """Sin esto, el password compartido es fuerza-bruteable sin limite."""
    for _ in range(5):
        cliente.post("/admin/login", data={"password": "mala", "next": "/"})
    r = cliente.post("/admin/login", data={"password": ADMIN_PASSWORD, "next": "/"})
    assert r.status_code == 429


def test_logout_borra_la_cookie_y_redirige_al_login(cliente: TestClient) -> None:
    r = cliente.get("/admin/logout", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "/admin/login"


def test_login_sin_admin_password_configurado_falla_con_mensaje_claro(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = Settings(token_db_path=tmp_path / "t.sqlite3", oura_state_secret="secreto-de-test")
    store = TokenStore(settings.token_db_path)
    mcp = create_mcp_server(settings, store)
    register_admin_routes(mcp, settings, store)
    c = TestClient(mcp.http_app(), base_url="https://testserver")

    r = c.post("/admin/login", data={"password": "cualquiera", "next": "/"})

    assert r.status_code == 500
    assert "ADMIN_PASSWORD" in r.text
