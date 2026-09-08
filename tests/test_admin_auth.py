from __future__ import annotations

import time

from oura_mcp_server.admin.auth import (
    ADMIN_SESSION_MAX_AGE_SECONDS,
    create_admin_session,
    is_valid_admin_session,
)


def test_una_sesion_recien_creada_es_valida() -> None:
    cookie = create_admin_session("secreto")
    assert is_valid_admin_session(cookie, "secreto") is True


def test_una_cookie_firmada_con_otro_secreto_es_invalida() -> None:
    cookie = create_admin_session("secreto")
    assert is_valid_admin_session(cookie, "otro-secreto") is False


def test_sin_cookie_es_invalida() -> None:
    assert is_valid_admin_session(None, "secreto") is False


def test_una_cookie_vencida_es_invalida(monkeypatch) -> None:
    cookie = create_admin_session("secreto")
    tiempo_real = time.time
    monkeypatch.setattr(time, "time", lambda: tiempo_real() + ADMIN_SESSION_MAX_AGE_SECONDS + 1)
    assert is_valid_admin_session(cookie, "secreto") is False
