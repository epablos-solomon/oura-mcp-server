from __future__ import annotations

from pathlib import Path

from oura_mcp_server.auth.token_store import TokenStore
from oura_mcp_server.models import OAuthTokens


def test_list_with_metadata_devuelve_tokens_y_fecha(tmp_path: Path) -> None:
    store = TokenStore(tmp_path / "t.sqlite3")
    store.save("kike", OAuthTokens(access_token="a", refresh_token="r", scope="daily"))
    store.save("amber", OAuthTokens(access_token="b"))

    registros = store.list_with_metadata()

    assert [r.user_id for r in registros] == ["amber", "kike"]
    kike = next(r for r in registros if r.user_id == "kike")
    assert kike.tokens.access_token == "a"
    assert kike.tokens.scope == "daily"
    assert kike.updated_at, "debe traer el timestamp de la fila"


def test_list_with_metadata_vacio_sin_datos(tmp_path: Path) -> None:
    store = TokenStore(tmp_path / "t.sqlite3")
    assert store.list_with_metadata() == []
