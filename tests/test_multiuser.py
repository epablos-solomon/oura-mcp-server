from pathlib import Path

import pytest

from oura_mcp_server.auth.state import sign_state, verify_state
from oura_mcp_server.auth.token_store import TokenStore
from oura_mcp_server.config import Settings
from oura_mcp_server.core.server import create_mcp_server

SECRET = "unit-test-secret"

EXPECTED_TOOLS = {
    "whoami", "sleep_summary", "readiness_summary", "activity_summary",
    "spo2_summary", "stress_summary", "resilience_summary", "cardiovascular_age",
    "sleep_periods", "sleep_time", "workouts", "sessions", "rest_mode_periods",
    "vo2_max", "enhanced_tags", "tags", "heartrate", "ring_configuration",
    "health_snapshot", "list_webhook_subscriptions", "create_webhook_subscription",
    "delete_webhook_subscription", "renew_webhook_subscription",
}


def test_state_roundtrip() -> None:
    st = sign_state("kike", SECRET)
    assert verify_state(st, SECRET) == "kike"


def test_state_rejects_tampering() -> None:
    st = sign_state("kike", SECRET)
    assert verify_state(st, "otro-secret") is None
    assert verify_state("basura", SECRET) is None
    assert verify_state(st[:-3] + "xyz", SECRET) is None


def test_state_expires(monkeypatch) -> None:
    from oura_mcp_server.auth import state as state_mod

    st = sign_state("kike", SECRET)
    # Simula que pasaron 601s desde la firma (limite por defecto: 600s).
    real = state_mod.time.time()
    monkeypatch.setattr(state_mod.time, "time", lambda: real + 601)
    assert verify_state(st, SECRET) is None


@pytest.mark.asyncio
async def test_all_tools_registered(tmp_path: Path) -> None:
    settings = Settings(token_db_path=tmp_path / "t.sqlite3", oura_state_secret=SECRET)
    store = TokenStore(settings.token_db_path)
    mcp = create_mcp_server(settings, store)
    names = {t.name for t in await mcp.list_tools()}
    assert EXPECTED_TOOLS <= names, f"faltan: {EXPECTED_TOOLS - names}"


def test_token_store_isolation(tmp_path: Path) -> None:
    from oura_mcp_server.models import OAuthTokens

    store = TokenStore(tmp_path / "t.sqlite3")
    store.save("kike", OAuthTokens(access_token="tok-kike"))
    store.save("amber", OAuthTokens(access_token="tok-amber"))
    assert store.get("kike").access_token == "tok-kike"
    assert store.get("amber").access_token == "tok-amber"
    assert store.get("desconocido") is None
