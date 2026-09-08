from __future__ import annotations

import time

from oura_mcp_server.admin.auth import (
    ADMIN_SESSION_MAX_AGE_SECONDS,
    LoginRateLimiter,
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


def test_permite_hasta_el_limite_de_intentos_fallidos() -> None:
    limiter = LoginRateLimiter(max_intentos=3, ventana_segundos=300)
    assert limiter.bloqueado() is False
    limiter.registrar_fallo()
    limiter.registrar_fallo()
    assert limiter.bloqueado() is False
    limiter.registrar_fallo()
    assert limiter.bloqueado() is True


def test_un_exito_resetea_el_contador() -> None:
    limiter = LoginRateLimiter(max_intentos=2, ventana_segundos=300)
    limiter.registrar_fallo()
    limiter.registrar_fallo()
    assert limiter.bloqueado() is True
    limiter.registrar_exito()
    assert limiter.bloqueado() is False


def test_los_fallos_expiran_fuera_de_la_ventana(monkeypatch) -> None:
    import time as time_mod

    limiter = LoginRateLimiter(max_intentos=1, ventana_segundos=1)
    limiter.registrar_fallo()
    assert limiter.bloqueado() is True
    tiempo_real = time_mod.time
    monkeypatch.setattr(time_mod, "time", lambda: tiempo_real() + 2)
    assert limiter.bloqueado() is False
