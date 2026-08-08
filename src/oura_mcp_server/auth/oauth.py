from __future__ import annotations

from urllib.parse import urlencode

import httpx

from oura_mcp_server.config import Settings
from oura_mcp_server.models import OAuthTokens


def scopes_faltantes(pedidos: str, concedidos: str | None) -> list[str]:
    """Scopes que se pidieron y Oura no concedio, en el orden en que se pidieron.

    Oura descarta en silencio los nombres que no reconoce y devuelve 200 con el
    subconjunto valido, prefijando cada uno con `extapi:`. Sin esta comparacion
    un scope mal escrito solo se nota mucho despues, como un 401 inexplicable
    en las tools que dependian de el.

    Si la respuesta no trae `scope` no hay nada que comparar: devuelve [] en vez
    de reportar todo como faltante.
    """
    if not concedidos:
        return []
    otorgados = {s.split(":", 1)[-1] for s in concedidos.split()}
    return [s for s in pedidos.split() if s not in otorgados]


class OuraOAuth2Manager:
    authorize_url = "https://cloud.ouraring.com/oauth/authorize"
    token_url = "https://api.ouraring.com/oauth/token"

    def __init__(self, settings: Settings):
        self.settings = settings

    def get_authorization_url(self, state: str) -> str:
        params = {
            "response_type": "code",
            "client_id": self.settings.oura_client_id,
            "redirect_uri": self.settings.oura_redirect_uri,
            "scope": self.settings.oura_scopes,
            "state": state,
        }
        return f"{self.authorize_url}?{urlencode(params)}"

    async def exchange_code(self, code: str) -> OAuthTokens:
        if not self.settings.oura_client_id or not self.settings.oura_client_secret:
            raise ValueError("Missing Oura OAuth client credentials")

        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                self.token_url,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": self.settings.oura_redirect_uri,
                    "client_id": self.settings.oura_client_id,
                    "client_secret": self.settings.oura_client_secret,
                },
            )
            r.raise_for_status()
            return OAuthTokens(**r.json())

    async def refresh(self, refresh_token: str) -> OAuthTokens:
        if not self.settings.oura_client_id or not self.settings.oura_client_secret:
            raise ValueError("Missing Oura OAuth client credentials")

        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                self.token_url,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": self.settings.oura_client_id,
                    "client_secret": self.settings.oura_client_secret,
                },
            )
            r.raise_for_status()
            return OAuthTokens(**r.json())
