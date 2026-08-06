"""Ruta de refresh de tokens OAuth.

Se sustituye solo el transporte de red (httpx.MockTransport). El TokenStore,
OuraClient y OuraOAuth2Manager son reales: lo que se comprueba es que el
refresh persiste los tokens nuevos bajo el user_id correcto y reintenta.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

from oura_mcp_server.auth.token_store import TokenStore
from oura_mcp_server.client.oura import OuraClient
from oura_mcp_server.config import Settings
from oura_mcp_server.models import OAuthTokens

TOKEN_URL = "https://api.ouraring.com/oauth/token"
SLEEP_PATH = "/usercollection/daily_sleep"
SLEEP_PAYLOAD = {"data": [{"day": "2026-08-05", "score": 82}], "next_token": None}

# Respuesta real del endpoint de token de Oura (rota el refresh_token).
REFRESHED_TOKEN_RESPONSE = {
    "token_type": "bearer",
    "access_token": "access-nuevo",
    "refresh_token": "refresh-nuevo",
    "expires_in": 86400,
    "scope": "daily personal",
}


def _install_oura_double(monkeypatch: pytest.MonkeyPatch, calls: list[tuple[str, str]]) -> None:
    """Enruta todo httpx a un doble de la API de Oura.

    - POST al endpoint de token -> devuelve REFRESHED_TOKEN_RESPONSE
    - GET a la API v2 -> 200 solo con el access token nuevo; 401 con el viejo
    """

    def handler(request: httpx.Request) -> httpx.Response:
        auth = request.headers.get("Authorization", "")
        calls.append((request.method, auth))
        if request.method == "POST" and str(request.url) == TOKEN_URL:
            return httpx.Response(200, json=REFRESHED_TOKEN_RESPONSE)
        if auth == "Bearer access-nuevo":
            return httpx.Response(200, json=SLEEP_PAYLOAD)
        return httpx.Response(401, json={"detail": "Unauthorized"})

    real_client = httpx.AsyncClient

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", factory)


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        oura_client_id="cid",
        oura_client_secret="csecret",
        token_db_path=tmp_path / "tokens.sqlite3",
    )


def _expired_tokens() -> OAuthTokens:
    return OAuthTokens(
        access_token="access-viejo",
        refresh_token="refresh-viejo",
        expires_in=86400,
        created_at=datetime.now(timezone.utc) - timedelta(days=2),
    )


async def test_refresh_guarda_tokens_nuevos_bajo_el_user_id_del_caller(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Token caducado: refresca, persiste para 'kike' y sirve la peticion."""
    settings = _settings(tmp_path)
    store = TokenStore(settings.token_db_path)
    store.save("kike", _expired_tokens())
    _install_oura_double(monkeypatch, calls := [])

    result = await OuraClient.get_json_for_user("kike", SLEEP_PATH, settings, store)

    assert result == SLEEP_PAYLOAD
    guardado = store.get("kike")
    assert guardado is not None
    assert guardado.access_token == "access-nuevo"
    assert guardado.refresh_token == "refresh-nuevo"
    # Los tokens de 'kike' no pueden acabar bajo la clave "default".
    assert store.get("default") is None
    assert calls == [("POST", ""), ("GET", "Bearer access-nuevo")]


async def test_refresh_tras_401_reintenta_con_el_token_nuevo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Token que parece vigente pero Oura responde 401: refresca y reintenta."""
    settings = _settings(tmp_path)
    store = TokenStore(settings.token_db_path)
    # expires_in vigente -> is_expired() es False, se intenta el GET directo.
    store.save(
        "kike",
        OAuthTokens(access_token="access-viejo", refresh_token="refresh-viejo", expires_in=86400),
    )
    _install_oura_double(monkeypatch, calls := [])

    result = await OuraClient.get_json_for_user("kike", SLEEP_PATH, settings, store)

    assert result == SLEEP_PAYLOAD
    assert store.get("kike").access_token == "access-nuevo"
    assert calls == [
        ("GET", "Bearer access-viejo"),  # 401
        ("POST", ""),                    # refresh
        ("GET", "Bearer access-nuevo"),  # reintento
    ]


async def test_sin_refresh_token_error_explicito_no_runtime_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sin refresh_token el fallo debe nombrar al usuario, no ser un raise vacio."""
    settings = _settings(tmp_path)
    store = TokenStore(settings.token_db_path)
    client = OuraClient(settings, "access-viejo")
    _install_oura_double(monkeypatch, [])

    with pytest.raises(ValueError, match="no_refresh_token: kike"):
        await client.refresh_and_retry(
            SLEEP_PATH, "kike", OAuthTokens(access_token="access-viejo"), store
        )
