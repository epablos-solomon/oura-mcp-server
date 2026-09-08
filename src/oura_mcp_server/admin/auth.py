"""Autenticación del panel /admin: password compartido + cookie de sesión firmada.

Reutiliza el HMAC de auth/state.py (mismo secreto OURA_STATE_SECRET) en vez de
montar un sistema de sesiones nuevo: un solo secreto protege tanto el `state`
de OAuth como el login de admin.
"""
from __future__ import annotations

import hashlib
import hmac

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


import time
from collections import defaultdict
from threading import Lock


class LoginRateLimiter:
    """Bloquea intentos de login tras varios fallos consecutivos.

    Un solo password compartido es fuerza-bruteable sin esto; el limite es
    generoso a proposito (5 intentos / 5 minutos) porque el unico admin real
    tambien puede equivocarse escribiendo el password.
    """

    def __init__(self, max_intentos: int = 5, ventana_segundos: int = 300):
        self.max_intentos = max_intentos
        self.ventana_segundos = ventana_segundos
        self._fallos: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def bloqueado(self, clave: str = "global") -> bool:
        with self._lock:
            ahora = time.time()
            recientes = [t for t in self._fallos[clave] if ahora - t < self.ventana_segundos]
            self._fallos[clave] = recientes
            return len(recientes) >= self.max_intentos

    def registrar_fallo(self, clave: str = "global") -> None:
        with self._lock:
            self._fallos[clave].append(time.time())

    def registrar_exito(self, clave: str = "global") -> None:
        with self._lock:
            self._fallos[clave] = []


def create_csrf_token(session_cookie: str, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), session_cookie.encode("utf-8"), hashlib.sha256).hexdigest()


def is_valid_csrf_token(token: str | None, session_cookie: str | None, secret: str) -> bool:
    if not token or not session_cookie:
        return False
    expected = create_csrf_token(session_cookie, secret)
    return hmac.compare_digest(token, expected)
