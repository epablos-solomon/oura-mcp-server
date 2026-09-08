"""Buffer en memoria de los ultimos avisos/errores para el panel de salud.

Se pierde al reiniciar el contenedor: es un vistazo rapido para el admin, no
un reemplazo de `docker logs` ni de logging persistente.
"""
from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass


@dataclass
class LogEntry:
    level: str
    logger_name: str
    message: str
    created_at: str


class InMemoryLogHandler(logging.Handler):
    def __init__(self, capacidad: int = 50):
        super().__init__(level=logging.WARNING)
        self._entradas: deque[LogEntry] = deque(maxlen=capacidad)
        self._formatter = logging.Formatter()

    def emit(self, record: logging.LogRecord) -> None:
        self._entradas.appendleft(
            LogEntry(
                level=record.levelname,
                logger_name=record.name,
                message=self.format(record),
                created_at=self._formatter.formatTime(record),
            )
        )

    def entries(self) -> list[LogEntry]:
        return list(self._entradas)
