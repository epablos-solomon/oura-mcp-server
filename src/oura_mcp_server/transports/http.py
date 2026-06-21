from __future__ import annotations

import secrets
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse

from oura_mcp_server.auth.oauth import OuraOAuth2Manager
from oura_mcp_server.auth.token_store import TokenStore
from oura_mcp_server.client.oura import OuraClient
from oura_mcp_server.config import Settings
from oura_mcp_server.core.server import create_mcp_server


def create_app(settings: Settings) -> FastAPI:
    app = FastAPI(title=settings.app_name, version="0.3.0")
    store = TokenStore(settings.token_db_path)
    oauth = OuraOAuth2Manager(settings)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": settings.app_name}

    @app.get("/auth/login")
    async def auth_login() -> RedirectResponse:
        if not settings.oura_client_id:
            raise HTTPException(status_code=400, detail="OURA_CLIENT_ID not configured")
        state = secrets.token_urlsafe(16)
        return RedirectResponse(oauth.get_authorization_url(state))

    @app.get("/auth/callback")
    async def auth_callback(code: str | None = None, state: str | None = None) -> dict[str, Any]:
        if not code:
            raise HTTPException(status_code=400, detail="Missing authorization code")
        tokens = await oauth.exchange_code(code)
        store.save("default", tokens)
        return {"status": "connected", "user_id": "default"}

    @app.get("/auth/refresh")
    async def auth_refresh() -> dict[str, Any]:
        tokens = store.get("default")
        if not tokens or not tokens.refresh_token:
            raise HTTPException(status_code=404, detail="No tokens or refresh token available")
        refreshed = await oauth.refresh(tokens.refresh_token)
        store.save("default", refreshed)
        return {"status": "refreshed"}

    @app.get("/api/snapshot")
    async def api_snapshot(start_date: str | None = None, end_date: str | None = None) -> dict[str, Any]:
        token = _resolve_bearer(settings, store)
        client = OuraClient(settings, token)
        params = {k: v for k, v in {"start_date": start_date, "end_date": end_date}.items() if v}
        import asyncio
        profile, sleep, readiness, activity = await asyncio.gather(
            client.get_json("/usercollection/personal_info"),
            client.get_json("/usercollection/daily_sleep", params),
            client.get_json("/usercollection/daily_readiness", params),
            client.get_json("/usercollection/daily_activity", params),
        )
        return {"profile": profile, "daily_sleep": sleep, "daily_readiness": readiness, "daily_activity": activity}

    @app.post("/webhooks/oura")
    async def oura_webhook(payload: dict[str, Any]) -> dict[str, Any]:
        return {"status": "received", "event_type": payload.get("event_type"), "data_type": payload.get("data_type")}

    return app


def _resolve_bearer(settings: Settings, store: TokenStore) -> str:
    if settings.oura_bearer_token:
        return settings.oura_bearer_token
    tokens = store.get("default")
    if not tokens:
        raise HTTPException(status_code=401, detail="No authentication configured")
    return tokens.access_token
