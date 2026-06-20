from fastapi.testclient import TestClient

from app.main import app
from app.models import OAuthTokens
from app.security import verify_oura_signature
from app.token_store import SQLiteTokenStore


def test_health():
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_token_store_roundtrip(tmp_path):
    store = SQLiteTokenStore(db_path=str(tmp_path / "tokens.sqlite3"))
    tokens = OAuthTokens(access_token="a", refresh_token="r", expires_in=3600)
    store.save("u1", tokens)
    got = store.get("u1")
    assert got is not None
    assert got.access_token == "a"
    assert store.list_user_ids() == ["u1"]


def test_signature_verification_false_for_empty_values():
    assert not verify_oura_signature("", b"body", "sig", "secret")


def test_import_mcp():
    from app.mcp_server import mcp

    assert mcp is not None
