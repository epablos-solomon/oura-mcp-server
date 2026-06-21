from __future__ import annotations

from typing import Any

import httpx

from oura_mcp_server.config import Settings
from oura_mcp_server.auth.token_store import TokenStore
from oura_mcp_server.auth.oauth import OuraOAuth2Manager


class OuraClient:
    def __init__(self, settings: Settings, access_token: str):
        self.settings = settings
        self.access_token = access_token
        self._oauth = OuraOAuth2Manager(settings)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.access_token}"}

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.settings.oura_api_base.rstrip('/')}/{path.lstrip('/')}"
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(url, headers=self._headers(), params=params)
            r.raise_for_status()
            return r.json()

    async def get_json(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self._get(path, params)

    async def refresh_and_retry(
        self, path: str, tokens, store: TokenStore, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        if tokens.refresh_token:
            new_tokens = await self._oauth.refresh(tokens.refresh_token)
            store.save(tokens.user_id or "default", new_tokens)
            self.access_token = new_tokens.access_token
            return await self._get(path, params)
        raise

    @classmethod
    async def get_json_for_user(
        cls,
        user_id: str,
        path: str,
        settings: Settings,
        store: TokenStore,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        tokens = store.get(user_id)
        if not tokens:
            raise ValueError(f"user_not_connected: {user_id}")

        client = cls(settings, tokens.access_token)

        if tokens.is_expired() and tokens.refresh_token:
            return await client.refresh_and_retry(path, tokens, store, params)

        try:
            return await client._get(path, params)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 401 or not tokens.refresh_token:
                raise
            return await client.refresh_and_retry(path, tokens, store, params)

    def _webhook_headers(self) -> dict[str, str]:
        return {
            "x-client-id": self.settings.oura_client_id or "",
            "x-client-secret": self.settings.oura_client_secret or "",
            "Content-Type": "application/json",
        }

    async def list_webhooks(self) -> list[dict]:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(
                f"{self.settings.oura_api_base}/webhook/subscription",
                headers=self._webhook_headers(),
            )
            r.raise_for_status()
            return r.json()

    async def create_webhook(self, callback_url: str, verification_token: str,
                             event_type: str = "update", data_type: str = "daily_sleep") -> dict:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{self.settings.oura_api_base}/webhook/subscription",
                headers=self._webhook_headers(),
                json={"callback_url": callback_url, "verification_token": verification_token,
                      "event_type": event_type, "data_type": data_type},
            )
            r.raise_for_status()
            return r.json()

    async def delete_webhook(self, subscription_id: str) -> None:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.delete(
                f"{self.settings.oura_api_base}/webhook/subscription/{subscription_id}",
                headers=self._webhook_headers(),
            )
            r.raise_for_status()

    async def renew_webhook(self, subscription_id: str) -> dict:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.put(
                f"{self.settings.oura_api_base}/webhook/subscription/renew/{subscription_id}",
                headers=self._webhook_headers(),
            )
            r.raise_for_status()
            return r.json()
