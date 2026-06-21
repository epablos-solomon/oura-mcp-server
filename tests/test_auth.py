from pathlib import Path

from oura_mcp_server.auth.token_store import TokenStore
from oura_mcp_server.models import OAuthTokens


def test_token_store_roundtrip(tmp_path: Path) -> None:
    db = tmp_path / "tokens.sqlite3"
    store = TokenStore(db)
    tokens = OAuthTokens(access_token="abc", refresh_token="ref")
    store.save("default", tokens)

    loaded = store.get("default")
    assert loaded is not None
    assert loaded.access_token == "abc"
    assert loaded.refresh_token == "ref"


def test_token_store_delete(tmp_path: Path) -> None:
    db = tmp_path / "tokens.sqlite3"
    store = TokenStore(db)
    store.save("u1", OAuthTokens(access_token="a"))
    store.delete("u1")
    assert store.get("u1") is None


def test_token_store_list(tmp_path: Path) -> None:
    db = tmp_path / "tokens.sqlite3"
    store = TokenStore(db)
    store.save("u1", OAuthTokens(access_token="a"))
    store.save("u2", OAuthTokens(access_token="b"))
    assert store.list_user_ids() == ["u1", "u2"]
