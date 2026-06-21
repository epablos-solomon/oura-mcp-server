from __future__ import annotations

import asyncio
from typing import Any

from mcp.server.fastmcp import FastMCP

from oura_mcp_server.auth.oauth import OuraOAuth2Manager
from oura_mcp_server.auth.token_store import TokenStore
from oura_mcp_server.client.oura import OuraClient
from oura_mcp_server.config import Settings


def _resolve_token(settings: Settings, store: TokenStore) -> str | None:
    """Returns a valid access token: bearer_token > stored tokens > None."""
    if settings.oura_bearer_token:
        return settings.oura_bearer_token
    tokens = store.get("default")
    return tokens.access_token if tokens else None


def create_mcp_server(settings: Settings, store: TokenStore) -> FastMCP:
    mcp = FastMCP(settings.mcp_name)

    def _ensure_token() -> str:
        token = _resolve_token(settings, store)
        if not token:
            raise RuntimeError(
                "No authentication configured. "
                "Set OURA_BEARER_TOKEN (dev) or run OAuth2 flow."
            )
        return token

    def _client() -> OuraClient:
        return OuraClient(settings, _ensure_token())

    @mcp.tool()
    async def whoami() -> dict[str, Any]:
        """Obtiene el perfil del usuario Oura conectado."""
        return await _client().get_json("/usercollection/personal_info")

    @mcp.tool()
    async def sleep_summary(start_date: str | None = None, end_date: str | None = None) -> dict[str, Any]:
        """Resumen de sueno en un rango de fechas."""
        params = {k: v for k, v in {"start_date": start_date, "end_date": end_date}.items() if v}
        return await _client().get_json("/usercollection/daily_sleep", params)

    @mcp.tool()
    async def readiness_summary(start_date: str | None = None, end_date: str | None = None) -> dict[str, Any]:
        """Resumen de readiness en un rango de fechas."""
        params = {k: v for k, v in {"start_date": start_date, "end_date": end_date}.items() if v}
        return await _client().get_json("/usercollection/daily_readiness", params)

    @mcp.tool()
    async def activity_summary(start_date: str | None = None, end_date: str | None = None) -> dict[str, Any]:
        """Resumen de actividad en un rango de fechas."""
        params = {k: v for k, v in {"start_date": start_date, "end_date": end_date}.items() if v}
        return await _client().get_json("/usercollection/daily_activity", params)

    @mcp.tool()
    async def health_snapshot(start_date: str | None = None, end_date: str | None = None) -> dict[str, Any]:
        """Snapshot completo: perfil + sueno + readiness + actividad."""
        params = {k: v for k, v in {"start_date": start_date, "end_date": end_date}.items() if v}
        c = _client()
        profile, sleep, readiness, activity = await asyncio.gather(
            c.get_json("/usercollection/personal_info"),
            c.get_json("/usercollection/daily_sleep", params),
            c.get_json("/usercollection/daily_readiness", params),
            c.get_json("/usercollection/daily_activity", params),
        )
        return {
            "profile": profile,
            "daily_sleep": sleep,
            "daily_readiness": readiness,
            "daily_activity": activity,
        }

    @mcp.tool()
    async def list_webhook_subscriptions() -> list[dict]:
        """Lista las suscripciones a webhooks de Oura."""
        return await _client().list_webhooks()

    @mcp.tool()
    async def create_webhook_subscription(
        callback_url: str,
        verification_token: str,
        event_type: str = "update",
        data_type: str = "daily_sleep",
    ) -> dict:
        """Crea una suscripcion a webhook de Oura."""
        return await _client().create_webhook(callback_url, verification_token, event_type, data_type)

    @mcp.tool()
    async def delete_webhook_subscription(subscription_id: str) -> dict:
        """Elimina una suscripcion a webhook."""
        await _client().delete_webhook(subscription_id)
        return {"ok": True}

    @mcp.tool()
    async def renew_webhook_subscription(subscription_id: str) -> dict:
        """Renueva una suscripcion a webhook."""
        return await _client().renew_webhook(subscription_id)

    @mcp.prompt()
    def daily_checkin() -> str:
        return (
            "Resume mi estado de salud de hoy basandote en los datos de Oura: "
            "sueno, readiness, actividad, y cualquier anomalia relevante."
        )

    return mcp
