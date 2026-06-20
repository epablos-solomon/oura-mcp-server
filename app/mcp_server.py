from __future__ import annotations

import asyncio

try:
    from mcp.server.fastmcp import FastMCP
except Exception:  # pragma: no cover - fallback for environments without mcp installed
    class FastMCP:  # type: ignore
        def __init__(self, name: str):
            self.name = name

        def tool(self):
            def decorator(fn):
                return fn
            return decorator

        def run(self):
            return None

from .oura_client import oura_client
from .token_store import token_store

mcp = FastMCP("oura-mcp-server")


def _range_params(start_date: str | None, end_date: str | None) -> dict[str, str]:
    return {k: v for k, v in {"start_date": start_date, "end_date": end_date}.items() if v}


@mcp.tool()
async def connect_account(user_id: str, redirect_uri: str | None = None) -> dict:
    state = f"{user_id}"
    return {"authorization_url": oura_client.build_authorize_url(state, redirect_uri), "state": state}


@mcp.tool()
async def get_profile(user_id: str) -> dict:
    return await oura_client.get_json_for_user(user_id, "/usercollection/personal_info", token_store)


@mcp.tool()
async def get_daily_sleep(user_id: str, start_date: str | None = None, end_date: str | None = None) -> dict:
    return await oura_client.get_json_for_user(
        user_id,
        "/usercollection/daily_sleep",
        token_store,
        _range_params(start_date, end_date),
    )


@mcp.tool()
async def get_daily_readiness(user_id: str, start_date: str | None = None, end_date: str | None = None) -> dict:
    return await oura_client.get_json_for_user(
        user_id,
        "/usercollection/daily_readiness",
        token_store,
        _range_params(start_date, end_date),
    )


@mcp.tool()
async def get_daily_activity(user_id: str, start_date: str | None = None, end_date: str | None = None) -> dict:
    return await oura_client.get_json_for_user(
        user_id,
        "/usercollection/daily_activity",
        token_store,
        _range_params(start_date, end_date),
    )


@mcp.tool()
async def get_health_snapshot(user_id: str, start_date: str | None = None, end_date: str | None = None) -> dict:
    params = _range_params(start_date, end_date)
    profile, sleep, readiness, activity = await asyncio.gather(
        oura_client.get_json_for_user(user_id, "/usercollection/personal_info", token_store),
        oura_client.get_json_for_user(user_id, "/usercollection/daily_sleep", token_store, params),
        oura_client.get_json_for_user(user_id, "/usercollection/daily_readiness", token_store, params),
        oura_client.get_json_for_user(user_id, "/usercollection/daily_activity", token_store, params),
    )
    return {
        "user_id": user_id,
        "profile": profile,
        "daily_sleep": sleep,
        "daily_readiness": readiness,
        "daily_activity": activity,
    }


@mcp.tool()
async def list_webhook_subscriptions() -> list[dict]:
    return await oura_client.list_webhook_subscriptions()


@mcp.tool()
async def create_webhook_subscription(
    callback_url: str,
    verification_token: str,
    event_type: str = "update",
    data_type: str = "daily_sleep",
) -> dict:
    return await oura_client.create_webhook_subscription(
        callback_url=callback_url,
        verification_token=verification_token,
        event_type=event_type,
        data_type=data_type,
    )


@mcp.tool()
async def renew_webhook_subscription(subscription_id: str) -> dict:
    return await oura_client.renew_webhook_subscription(subscription_id)


@mcp.tool()
async def delete_webhook_subscription(subscription_id: str) -> dict:
    await oura_client.delete_webhook_subscription(subscription_id)
    return {"ok": True}


if __name__ == "__main__":
    mcp.run()
