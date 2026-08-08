"""Oura descarta en silencio los scopes que no reconoce.

Devuelve 200 con el subconjunto valido, asi que un nombre mal escrito
(`spo2Daily` en vez de `spo2`) no da error: las tools que dependen de el
empiezan a devolver 401 sin nada que apunte a la causa.
"""
from __future__ import annotations

from oura_mcp_server.auth.oauth import scopes_faltantes
from oura_mcp_server.config import Settings

# Formato real de la respuesta de Oura: los concedidos llevan prefijo extapi:.
CONCEDIDOS_REALES = (
    "extapi:email extapi:personal extapi:daily extapi:heartrate "
    "extapi:workout extapi:tag extapi:session"
)


def test_detecta_el_scope_que_oura_no_concedio() -> None:
    """El caso que nos paso en produccion: spo2Daily pedido, nunca concedido."""
    pedidos = "email personal daily heartrate workout tag session spo2Daily"
    assert scopes_faltantes(pedidos, CONCEDIDOS_REALES) == ["spo2Daily"]


def test_sin_diferencias_no_reporta_nada() -> None:
    pedidos = "email personal daily heartrate workout tag session"
    assert scopes_faltantes(pedidos, CONCEDIDOS_REALES) == []


def test_reporta_varios_en_el_orden_pedido() -> None:
    pedidos = "email spo2 personal stress daily"
    assert scopes_faltantes(pedidos, CONCEDIDOS_REALES) == ["spo2", "stress"]


def test_sin_scope_en_la_respuesta_no_inventa_faltantes() -> None:
    """Si Oura no devuelve `scope` no hay nada que comparar: no alarmar en falso."""
    assert scopes_faltantes("email personal", None) == []
    assert scopes_faltantes("email personal", "") == []


def test_los_scopes_por_defecto_usan_los_identificadores_de_oura() -> None:
    """Nombres reales de la API v2; `spo2Daily` no existe."""
    pedidos = set(Settings().oura_scopes.split())
    assert "spo2" in pedidos
    assert "spo2Daily" not in pedidos
    # Scopes habilitados en la app de Oura que las tools necesitan.
    assert {"stress", "heart_health", "ring_configuration"} <= pedidos
