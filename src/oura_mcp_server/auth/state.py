"""Signed, time-limited OAuth `state` parameter.

The OAuth callback from Oura must be tied back to the right person. We encode
the oura_user_id into a signed `state` so the callback can recover it without a
server-side session store. Uses stdlib HMAC-SHA256 — no extra dependency.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64d(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


def sign_state(user_id: str, secret: str) -> str:
    payload = {"uid": user_id, "ts": int(time.time()), "n": secrets.token_hex(8)}
    body = _b64e(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    sig = hmac.new(secret.encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest()
    return f"{body}.{_b64e(sig)}"


def verify_state(state: str, secret: str, max_age_seconds: int = 600) -> str | None:
    """Returns the user_id if the state is valid and fresh, else None."""
    try:
        body, sig = state.split(".", 1)
    except ValueError:
        return None
    expected = hmac.new(secret.encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest()
    if not hmac.compare_digest(_b64d(sig), expected):
        return None
    try:
        payload = json.loads(_b64d(body))
    except (ValueError, json.JSONDecodeError):
        return None
    if int(time.time()) - int(payload.get("ts", 0)) > max_age_seconds:
        return None
    uid = payload.get("uid")
    return uid if isinstance(uid, str) and uid else None
