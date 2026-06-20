import secrets

from fastapi import APIRouter, Header, HTTPException, Query, Request

from .models import ConnectAccountResponse, HealthResponse
from .oura_client import oura_client
from .security import verify_oura_signature
from .settings import settings
from .token_store import token_store

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse()


@router.get("/tokens/users")
def list_users():
    return {"user_ids": token_store.list_user_ids()}


@router.get("/oauth/start", response_model=ConnectAccountResponse)
def oauth_start(user_id: str = Query(...), redirect_uri: str | None = None):
    state = f"{user_id}:{secrets.token_urlsafe(16)}"
    return ConnectAccountResponse(
        authorization_url=oura_client.build_authorize_url(state, redirect_uri),
        state=state,
    )


@router.get("/oauth/callback")
async def oauth_callback(code: str | None = None, error: str | None = None, state: str | None = None):
    if error:
        raise HTTPException(status_code=400, detail=error)
    if not code or not state:
        raise HTTPException(status_code=400, detail="missing_code_or_state")

    user_id = state.split(":", 1)[0]
    tokens = await oura_client.exchange_code(code)
    token_store.save(user_id, tokens)
    return {"ok": True, "user_id": user_id}


@router.post("/webhooks/oura")
async def oura_webhook(
    request: Request,
    x_oura_signature: str | None = Header(default=None),
    x_oura_timestamp: str | None = Header(default=None),
):
    body = await request.body()
    if settings.oura_webhook_verification_token:
        ok = verify_oura_signature(
            x_oura_timestamp or "",
            body,
            x_oura_signature or "",
            settings.oura_webhook_verification_token,
        )
        if not ok:
            raise HTTPException(status_code=401, detail="invalid_signature")
    return {"ok": True}


@router.get("/webhooks/oura/subscriptions")
async def list_webhook_subscriptions():
    return await oura_client.list_webhook_subscriptions()


@router.post("/webhooks/oura/subscriptions")
async def create_webhook_subscription(
    callback_url: str,
    verification_token: str,
    event_type: str = "update",
    data_type: str = "daily_sleep",
):
    return await oura_client.create_webhook_subscription(
        callback_url=callback_url,
        verification_token=verification_token,
        event_type=event_type,
        data_type=data_type,
    )


@router.delete("/webhooks/oura/subscriptions/{subscription_id}")
async def delete_webhook_subscription(subscription_id: str):
    await oura_client.delete_webhook_subscription(subscription_id)
    return {"ok": True}


@router.put("/webhooks/oura/subscriptions/{subscription_id}/renew")
async def renew_webhook_subscription(subscription_id: str):
    return await oura_client.renew_webhook_subscription(subscription_id)
