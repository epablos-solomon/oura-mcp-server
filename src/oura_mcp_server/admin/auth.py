"""Autenticación del panel /admin: password compartido + cookie de sesión firmada.

Reutiliza el HMAC de auth/state.py (mismo secreto OURA_STATE_SECRET) en vez de
montar un sistema de sesiones nuevo: un solo secreto protege tanto el `state`
de OAuth como el login de admin.
"""
from __future__ import annotations

from oura_mcp_server.auth.state import sign_state, verify_state

ADMIN_SESSION_SUBJECT = "admin"
ADMIN_SESSION_MAX_AGE_SECONDS = 12 * 60 * 60  # 12h
ADMIN_SESSION_COOKIE = "admin_session"


def create_admin_session(secret: str) -> str:
    return sign_state(ADMIN_SESSION_SUBJECT, secret)


def is_valid_admin_session(cookie_value: str | None, secret: str) -> bool:
    if not cookie_value:
        return False
    subject = verify_state(cookie_value, secret, max_age_seconds=ADMIN_SESSION_MAX_AGE_SECONDS)
    return subject == ADMIN_SESSION_SUBJECT
