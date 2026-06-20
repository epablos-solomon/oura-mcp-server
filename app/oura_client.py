from __future__ import annotations

import base64
from urllib.parse import urlencode

import httpx

from .models import OAuthTokens
from .settings import settings


class OuraClient:
    def build_authorize_url(self, state: str, redirect_uri: str | None = None) -> str:
        params = {
            "response_type": "code",
            "client_id": settings.oura_client_id,
            "redirect_uri": redirect_uri or settings.oura_redirect_uri,
            "scope": settings.oura_scopes,
            "state": state,
        }
        return f"{settings.oura_authorize_url}?{urlencode(params)}"

    def _basic_auth_header(self) -> str:
        auth = base64.b64encode(
            f"{settings.oura_client_id}:{settings.oura_client_secret}".encode()
        ).decode()
        return f"Basic {auth}"

    async def exchange_code(self, code: str, redirect_uri: str | None = None) -> OAuthTokens:
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri or settings.oura_redirect_uri,
        }
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                settings.oura_token_url,
                data=data,
                headers={"Authorization": self._basic_auth_header()},
            )
            r.raise_for_status()
            return OAuthTokens(**r.json())

    async def refresh(self, refresh_token: str) -> OAuthTokens:
        data = {"grant_type": "refresh_token", "refresh_token": refresh_token}
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                settings.oura_token_url,
                data=data,
                headers={"Authorization": self._basic_auth_header()},
            )
            r.raise_for_status()
            return OAuthTokens(**r.json())

    async def get_json(self, path: str, access_token: str, params: dict | None = None):
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(
                f"{settings.oura_api_base}{path}",
                headers={"Authorization": f"Bearer {access_token}"},
                params=params,
            )
            r.raise_for_status()
            return r.json()

    async def get_json_for_user(self, user_id: str, path: str, store, params: dict | None = None):
        tokens = store.get(user_id)
        if not tokens:
            raise ValueError("user_not_connected")

        if tokens.is_expired() and tokens.refresh_token:
            tokens = await self.refresh(tokens.refresh_token)
            store.save(user_id, tokens)

        try:
            return await self.get_json(path, tokens.access_token, params)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 401 or not tokens.refresh_token:
                raise
            tokens = await self.refresh(tokens.refresh_token)
            store.save(user_id, tokens)
            return await self.get_json(path, tokens.access_token, params)

    def webhook_headers(self) -> dict[str, str]:
        return {
            "x-client-id": settings.oura_client_id,
            "x-client-secret": settings.oura_client_secret,
            "Content-Type": "application/json",
        }

    async def list_webhook_subscriptions(self) -> list[dict]:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(
                f"{settings.oura_api_base}/webhook/subscription",
                headers=self.webhook_headers(),
            )
            r.raise_for_status()
            return r.json()

    async def create_webhook_subscription(
        self,
        callback_url: str,
        verification_token: str,
        event_type: str,
        data_type: str,
    ) -> dict:
        payload = {
            "callback_url": callback_url,
            "verification_token": verification_token,
            "event_type": event_type,
            "data_type": data_type,
        }
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{settings.oura_api_base}/webhook/subscription",
                headers=self.webhook_headers(),
                json=payload,
            )
            r.raise_for_status()
            return r.json()

    async def delete_webhook_subscription(self, subscription_id: str) -> None:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.delete(
                f"{settings.oura_api_base}/webhook/subscription/{subscription_id}",
                headers=self.webhook_headers(),
            )
            r.raise_for_status()

    async def renew_webhook_subscription(self, subscription_id: str) -> dict:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.put(
                f"{settings.oura_api_base}/webhook/subscription/renew/{subscription_id}",
                headers=self.webhook_headers(),
            )
            r.raise_for_status()
            return r.json()


oura_client = OuraClient()
