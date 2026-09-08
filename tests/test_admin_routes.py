"""Panel de administracion (/admin/*): login, tenants, OAuth, webhooks, salud."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

import httpx
import pytest
from starlette.testclient import TestClient

from oura_mcp_server.admin.auth import ADMIN_SESSION_COOKIE
from oura_mcp_server.admin.routes import register_admin_routes
from oura_mcp_server.auth import tenants as tenants_mod
from oura_mcp_server.auth.tenants import resolve_tenant
from oura_mcp_server.auth.token_store import TokenStore
from oura_mcp_server.config import Settings
from oura_mcp_server.core.server import create_mcp_server
from oura_mcp_server.models import OAuthTokens

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


def test_login_sin_oura_state_secret_configurado_falla_con_mensaje_claro(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = Settings(token_db_path=tmp_path / "t.sqlite3", admin_password=ADMIN_PASSWORD)
    store = TokenStore(settings.token_db_path)
    mcp = create_mcp_server(settings, store)
    register_admin_routes(mcp, settings, store)
    c = TestClient(mcp.http_app(), base_url="https://testserver")

    r = c.post("/admin/login", data={"password": ADMIN_PASSWORD, "next": "/"})

    assert r.status_code == 500
    assert "OURA_STATE_SECRET" in r.text


# --- next: XSS reflejado y open redirect ---

def test_next_con_html_no_se_refleja_sin_escapar(cliente: TestClient) -> None:
    """El parametro `next` viaja al form: si no se escapa, rompe el atributo HTML."""
    r = cliente.get('/admin/login?next="><script>alert(1)</script>')
    assert r.status_code == 200
    assert "<script>alert(1)</script>" not in r.text


def test_next_absoluto_al_loguear_no_produce_open_redirect(cliente: TestClient) -> None:
    """Un `next` a otro dominio no debe redirigir fuera del sitio tras login."""
    r = cliente.post(
        "/admin/login",
        data={"password": ADMIN_PASSWORD, "next": "https://evil.example/phish"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"] != "https://evil.example/phish"
    assert r.headers["location"] == "/admin/tenants"


# --- Panel de tenants/keys ---

def test_get_tenants_sin_sesion_redirige_al_login(cliente: TestClient) -> None:
    r = cliente.get("/admin/tenants", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"].startswith("/admin/login")


def test_get_tenants_lista_las_keys_enmascaradas(cliente: TestClient) -> None:
    _login(cliente)
    r = cliente.get("/admin/tenants")
    assert r.status_code == 200
    assert "sk-oura-kike-existente" not in r.text
    assert "kike" in r.text


def test_crear_key_la_reconoce_de_inmediato_sin_reiniciar(cliente: TestClient) -> None:
    _login(cliente)
    csrf = _csrf_de(cliente)
    r = cliente.post(
        "/admin/tenants/create",
        data={"csrf": csrf, "tenant_id": "scaleflow", "tenant_name": "Scaleflow Internal",
              "user": "amber", "agent": "openclaw"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    reveal_url = r.headers["location"]
    pagina = cliente.get(reveal_url)
    key = re.search(r"sk-oura-amber-[0-9a-f]+", pagina.text).group(0)

    assert resolve_tenant(key) is not None


def test_la_key_no_se_vuelve_a_mostrar_en_una_segunda_visita(cliente: TestClient) -> None:
    """La key completa solo se ve una vez: la URL de revelado es de un solo uso."""
    _login(cliente)
    csrf = _csrf_de(cliente)
    r = cliente.post(
        "/admin/tenants/create",
        data={"csrf": csrf, "tenant_id": "scaleflow", "tenant_name": "Scaleflow Internal",
              "user": "amber", "agent": "openclaw"},
        follow_redirects=False,
    )
    reveal_url = r.headers["location"]
    cliente.get(reveal_url)
    segunda = cliente.get(reveal_url)
    assert "sk-oura-amber-" not in segunda.text


def test_crear_key_sin_csrf_rechaza(cliente: TestClient) -> None:
    _login(cliente)
    r = cliente.post(
        "/admin/tenants/create",
        data={"tenant_id": "scaleflow", "tenant_name": "x", "user": "amber", "agent": "y"},
    )
    assert r.status_code == 403


def test_revocar_key_la_invalida_de_inmediato_sin_reiniciar(cliente: TestClient) -> None:
    _login(cliente)
    csrf = _csrf_de(cliente)
    key_id = hashlib.sha256(b"sk-oura-kike-existente").hexdigest()[:12]

    r = cliente.post(
        "/admin/tenants/revoke", data={"csrf": csrf, "key_id": key_id}, follow_redirects=False
    )

    assert r.status_code == 303
    assert resolve_tenant("sk-oura-kike-existente") is None


# --- Panel de estado OAuth ---

def test_get_oauth_sin_sesion_redirige_al_login(cliente: TestClient) -> None:
    r = cliente.get("/admin/oauth", follow_redirects=False)
    assert r.status_code == 302


def test_oauth_lista_usuarios_con_key_sin_conectar_y_conectados(cliente: TestClient) -> None:
    cliente.store.save("kike", OAuthTokens(access_token="a", refresh_token="r", scope="daily email"))
    _login(cliente)

    r = cliente.get("/admin/oauth")

    assert r.status_code == 200
    assert "kike" in r.text
    assert "daily email" in r.text


def test_oauth_marca_no_conectado_a_quien_tiene_key_pero_nunca_hizo_oauth(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reproduce el criterio central de la tarea: personas con key sin
    conectar deben listarse como "no conectado", separadas de quienes si
    completaron el flujo OAuth. Usa un tenants.yaml propio con dos usuarios
    (amber nunca hace `store.save`) para no depender de la fixture
    compartida, que solo define a `kike`.
    """
    tenants_yaml = """
default_tenant: scaleflow
tenants:
  scaleflow:
    name: Scaleflow Internal
    api_keys:
      - key: sk-oura-kike-existente
        agent: claude-code
        user: kike
      - key: sk-oura-amber-existente
        agent: openclaw
        user: amber
"""
    (tmp_path / "tenants.yaml").write_text(tenants_yaml)
    settings = Settings(
        token_db_path=tmp_path / "t.sqlite3",
        oura_state_secret="secreto-de-test",
        oura_client_id="cid",
        oura_client_secret="csec",
        tenants_config_path=str(tmp_path / "tenants.yaml"),
        admin_password=ADMIN_PASSWORD,
    )
    monkeypatch.setattr(tenants_mod, "get_settings", lambda: settings)
    tenants_mod.reload()

    store = TokenStore(settings.token_db_path)
    mcp = create_mcp_server(settings, store)
    register_admin_routes(mcp, settings, store)
    c = TestClient(mcp.http_app(), base_url="https://testserver")
    c.store = store

    c.store.save("kike", OAuthTokens(access_token="a", refresh_token="r"))
    _login(c)

    r = c.get("/admin/oauth")

    assert r.status_code == 200
    assert "amber" in r.text
    assert "no conectado" in r.text
    kike_row = re.search(r"<tr><td>kike</td>.*?</tr>", r.text)
    assert kike_row, "no se encontro la fila de kike"
    assert "no conectado" not in kike_row.group(0)
    assert "conectado" in kike_row.group(0)

    tenants_mod._key_lookup = None
    tenants_mod._default_tenant = None


def test_forzar_reconexion_borra_los_tokens_guardados(cliente: TestClient) -> None:
    cliente.store.save("kike", OAuthTokens(access_token="a", refresh_token="r"))
    _login(cliente)
    csrf = _csrf_de(cliente, "/admin/oauth")

    r = cliente.post(
        "/admin/oauth/desconectar", data={"csrf": csrf, "user_id": "kike"}, follow_redirects=False
    )

    assert r.status_code == 303
    assert cliente.store.get("kike") is None


def test_desconectar_sin_csrf_rechaza(cliente: TestClient) -> None:
    cliente.store.save("kike", OAuthTokens(access_token="a"))
    _login(cliente)

    r = cliente.post("/admin/oauth/desconectar", data={"user_id": "kike"})

    assert r.status_code == 403
    assert cliente.store.get("kike") is not None


def _mock_oura_webhooks(monkeypatch: pytest.MonkeyPatch, respuestas: dict) -> list[str]:
    """Sustituye httpx.AsyncClient por un doble que responde segun el metodo HTTP."""
    llamadas: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        llamadas.append(request.method)
        status, payload = respuestas.get(request.method, (200, {}))
        return httpx.Response(status, json=payload)

    real_client = httpx.AsyncClient

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", factory)
    return llamadas


# --- Panel de webhooks ---

def test_webhooks_sin_credenciales_configuradas_muestra_aviso(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "tenants.yaml").write_text(TENANTS_YAML)
    settings = Settings(
        token_db_path=tmp_path / "t.sqlite3",
        oura_state_secret="secreto-de-test",
        tenants_config_path=str(tmp_path / "tenants.yaml"),
        admin_password=ADMIN_PASSWORD,
    )
    monkeypatch.setattr(tenants_mod, "get_settings", lambda: settings)
    tenants_mod.reload()
    store = TokenStore(settings.token_db_path)
    mcp = create_mcp_server(settings, store)
    register_admin_routes(mcp, settings, store)
    c = TestClient(mcp.http_app(), base_url="https://testserver")

    _login(c)
    r = c.get("/admin/webhooks")

    assert "no se pueden" in r.text.lower()
    tenants_mod._key_lookup = None
    tenants_mod._default_tenant = None


def test_webhooks_lista_las_suscripciones_existentes(
    cliente: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _mock_oura_webhooks(
        monkeypatch,
        {"GET": (200, [{"id": "sub-1", "callback_url": "https://x/webhooks/oura",
                        "event_type": "update", "data_type": "daily_sleep"}])},
    )
    _login(cliente)

    r = cliente.get("/admin/webhooks")

    assert r.status_code == 200
    assert "sub-1" in r.text


def test_crear_webhook_llama_a_la_api_con_los_datos_del_form(
    cliente: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    llamadas = _mock_oura_webhooks(monkeypatch, {"POST": (200, {"id": "nuevo"})})
    _login(cliente)
    # CSRF depende solo de la sesion (no de la ruta): se pide en /admin/tenants
    # para no contaminar `llamadas` con el GET que /admin/webhooks hace a Oura.
    csrf = _csrf_de(cliente)

    r = cliente.post(
        "/admin/webhooks/crear",
        data={"csrf": csrf, "callback_url": "https://oura.scaleflow.tech/webhooks/oura",
              "verification_token": "tok", "event_type": "update", "data_type": "daily_sleep"},
        follow_redirects=False,
    )

    assert r.status_code == 303
    assert llamadas == ["POST"]


def test_eliminar_webhook_sin_csrf_rechaza(
    cliente: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    llamadas = _mock_oura_webhooks(monkeypatch, {"DELETE": (200, {})})
    _login(cliente)

    r = cliente.post("/admin/webhooks/eliminar", data={"subscription_id": "sub-1"})

    assert r.status_code == 403
    assert llamadas == []


def test_error_de_la_api_de_oura_se_muestra_sin_reventar(
    cliente: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _mock_oura_webhooks(monkeypatch, {"GET": (401, {"detail": "bad creds"})})
    _login(cliente)

    r = cliente.get("/admin/webhooks")

    assert r.status_code == 200
    assert "error" in r.text.lower()
