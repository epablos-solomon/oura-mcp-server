from __future__ import annotations

import logging

from oura_mcp_server.admin.log_buffer import InMemoryLogHandler


def test_captura_warnings_y_errores_pero_no_info() -> None:
    handler = InMemoryLogHandler(capacidad=10)
    logger = logging.getLogger("oura_mcp_server.test_log_buffer")
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    logger.info("esto no se guarda")
    logger.warning("cuidado")
    logger.error("fallo")

    entradas = handler.entries()
    assert len(entradas) == 2
    assert entradas[0].message == "fallo"  # el mas reciente primero
    assert entradas[1].message == "cuidado"

    logger.removeHandler(handler)


def test_respeta_la_capacidad_maxima() -> None:
    handler = InMemoryLogHandler(capacidad=2)
    logger = logging.getLogger("oura_mcp_server.test_log_buffer_cap")
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    for i in range(5):
        logger.warning("aviso %d", i)

    assert len(handler.entries()) == 2
    assert handler.entries()[0].message == "aviso 4"

    logger.removeHandler(handler)
