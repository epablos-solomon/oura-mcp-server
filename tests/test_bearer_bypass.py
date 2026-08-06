"""OURA_BEARER_TOKEN no puede saltarse la identidad en el transporte HTTP.

Es un atajo legitimo de desarrollo para stdio (un solo usuario). Pero si esta
puesto en el .env del contenedor HTTP, todos los tenants leerian los datos de
salud de esa unica persona. La senal de "esto es HTTP multiusuario" es que
create_mcp_server recibe un `auth`.
"""
from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from fastmcp import Client

from oura_mcp_server.auth.api_key_auth import ApiKeyAuthProvider
from oura_mcp_server.auth.token_store import TokenStore
from oura_mcp_server.config import Settings
from oura_mcp_server.core.server import create_mcp_server

PERFIL = {"id": "oura-123", "email": "kike@example.com", "age": 38, "sex": "male"}


def _capturar_peticiones(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    """Enruta httpx a un doble y devuelve la lista (url, Authorization) observada."""
    peticiones: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        peticiones.append((str(request.url), request.headers.get("Authorization", "")))
        return httpx.Response(200, json=PERFIL)

    real_client = httpx.AsyncClient

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", factory)
    return peticiones


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        oura_bearer_token="dev-token-de-kike",
        token_db_path=tmp_path / "tokens.sqlite3",
    )


async def test_http_con_auth_ignora_el_bearer_global(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Con auth (HTTP multiusuario) no se toca la API con el bearer compartido."""
    settings = _settings(tmp_path)
    store = TokenStore(settings.token_db_path)
    mcp = create_mcp_server(settings, store, auth=ApiKeyAuthProvider())
    peticiones = _capturar_peticiones(monkeypatch)

    async with Client(mcp) as client:
        with pytest.raises(Exception, match="no ha conectado"):
            await client.call_tool("whoami", {})

    assert peticiones == [], "no debe salir ninguna peticion con el bearer compartido"


async def test_stdio_sin_auth_sigue_usando_el_bearer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sin auth (stdio, un solo usuario) el atajo de desarrollo sigue vivo."""
    settings = _settings(tmp_path)
    store = TokenStore(settings.token_db_path)
    mcp = create_mcp_server(settings, store, auth=None)
    peticiones = _capturar_peticiones(monkeypatch)

    async with Client(mcp) as client:
        await client.call_tool("whoami", {})

    assert peticiones == [
        ("https://api.ouraring.com/v2/usercollection/personal_info", "Bearer dev-token-de-kike")
    ]
