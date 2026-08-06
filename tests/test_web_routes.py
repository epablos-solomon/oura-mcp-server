"""Rutas HTTP auxiliares: handshake del webhook y entrega de la API key.

Se levantan las rutas reales sobre la app Starlette que expone FastMCP; solo
el YAML de tenants es de test.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from starlette.testclient import TestClient

from oura_mcp_server.auth import tenants as tenants_mod
from oura_mcp_server.auth.token_store import TokenStore
from oura_mcp_server.config import Settings
from oura_mcp_server.core.server import create_mcp_server
from oura_mcp_server.core.web_routes import register_web_routes

TENANTS_YAML = """
default_tenant: scaleflow
tenants:
  scaleflow:
    name: Scaleflow Internal
    api_keys:
      - key: sk-test-kike
        agent: claude-code
        user: kike
"""
WEBHOOK_TOKEN = "token-de-verificacion-secreto"


@pytest.fixture
def cliente(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    (tmp_path / "tenants.yaml").write_text(TENANTS_YAML)
    settings = Settings(
        token_db_path=tmp_path / "t.sqlite3",
        oura_state_secret="secreto-de-test",
        oura_client_id="cid",
        oura_client_secret="csec",
        oura_redirect_uri="https://oura.example/auth/callback",
        oura_webhook_verification_token=WEBHOOK_TOKEN,
        tenants_config_path=str(tmp_path / "tenants.yaml"),
    )
    # tenants.py lee la config por get_settings(), no por el objeto que se pasa.
    monkeypatch.setattr(tenants_mod, "get_settings", lambda: settings)
    tenants_mod.reload()

    store = TokenStore(settings.token_db_path)
    mcp = create_mcp_server(settings, store)
    register_web_routes(mcp, settings, store)
    yield TestClient(mcp.http_app())

    tenants_mod._key_lookup = None
    tenants_mod._default_tenant = None


# --- Webhook: handshake de verificacion ---

def test_webhook_devuelve_el_challenge_con_el_token_correcto(cliente: TestClient) -> None:
    r = cliente.get(f"/webhooks/oura?verification_token={WEBHOOK_TOKEN}&challenge=abc123")
    assert r.status_code == 200
    assert r.json() == {"challenge": "abc123"}


def test_webhook_rechaza_un_token_incorrecto(cliente: TestClient) -> None:
    """Sin esto, cualquiera confirma suscripciones en nuestro nombre."""
    r = cliente.get("/webhooks/oura?verification_token=token-equivocado&challenge=abc123")
    assert r.status_code == 401
    assert "abc123" not in r.text


def test_webhook_sin_token_en_la_peticion_rechaza(cliente: TestClient) -> None:
    r = cliente.get("/webhooks/oura?challenge=abc123")
    assert r.status_code == 401
    assert "abc123" not in r.text


def test_webhook_sin_token_configurado_falla_cerrado(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Si no hemos configurado el token, no podemos verificar: 503, no 200."""
    settings = Settings(
        token_db_path=tmp_path / "t.sqlite3",
        oura_state_secret="secreto-de-test",
        oura_webhook_verification_token=None,
    )
    store = TokenStore(settings.token_db_path)
    mcp = create_mcp_server(settings, store)
    register_web_routes(mcp, settings, store)

    with TestClient(mcp.http_app()) as c:
        r = c.get("/webhooks/oura?verification_token=lo-que-sea&challenge=abc123")
        assert r.status_code == 503
        assert "abc123" not in r.text


# --- /auth/login: la API key va en el cuerpo, nunca en la URL ---

def test_get_login_muestra_el_formulario(cliente: TestClient) -> None:
    r = cliente.get("/auth/login")
    assert r.status_code == 200
    assert 'type="password"' in r.text
    assert 'name="key"' in r.text
    assert r.headers["cache-control"] == "no-store"


def test_get_login_ya_no_acepta_la_key_en_la_url(cliente: TestClient) -> None:
    """El ?key= dejaba la credencial en los logs de Caddy y en el historial."""
    r = cliente.get("/auth/login?key=sk-test-kike", follow_redirects=False)
    assert r.status_code == 200, "debe mostrar el formulario, no redirigir a Oura"
    assert "cloud.ouraring.com" not in r.headers.get("location", "")


def test_post_login_con_key_valida_redirige_a_oura(cliente: TestClient) -> None:
    r = cliente.post("/auth/login", data={"key": "sk-test-kike"}, follow_redirects=False)
    assert r.status_code in (302, 303, 307)
    destino = r.headers["location"]
    assert destino.startswith("https://cloud.ouraring.com/oauth/authorize")
    assert "state=" in destino
    assert "sk-test-kike" not in destino, "la API key no puede viajar hacia Oura"


def test_post_login_con_key_invalida_rechaza(cliente: TestClient) -> None:
    r = cliente.post("/auth/login", data={"key": "sk-inventada"}, follow_redirects=False)
    assert r.status_code == 401
    assert "location" not in r.headers


def test_post_login_sin_key_pide_la_key(cliente: TestClient) -> None:
    r = cliente.post("/auth/login", data={}, follow_redirects=False)
    assert r.status_code == 400
