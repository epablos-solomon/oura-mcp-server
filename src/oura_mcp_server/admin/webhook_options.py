"""Enums oficiales de la API de webhooks de Oura (ExtApiV2DataType / WebhookOperation).

El formulario del panel los ofrece como <select> para no adivinar typos:
Oura descarta o rechaza los nombres que no reconoce.
"""
from __future__ import annotations

from html import escape

# create / update / delete — schema WebhookOperation
WEBHOOK_EVENT_TYPES: tuple[tuple[str, str], ...] = (
    ("update", "Actualizar (update)"),
    ("create", "Crear (create)"),
    ("delete", "Eliminar (delete)"),
)

# ExtApiV2DataType de la OpenAPI v2 de Oura (cloud.ouraring.com)
WEBHOOK_DATA_TYPES: tuple[tuple[str, str], ...] = (
    ("daily_sleep", "Sueño diario"),
    ("daily_readiness", "Readiness diario"),
    ("daily_activity", "Actividad diaria"),
    ("daily_spo2", "SpO2 diario"),
    ("daily_stress", "Estrés diario"),
    ("daily_resilience", "Resiliencia diaria"),
    ("daily_cardiovascular_age", "Edad cardiovascular"),
    ("sleep", "Periodos de sueño"),
    ("sleep_time", "Tiempo de sueño"),
    ("workout", "Entrenamiento"),
    ("session", "Sesión"),
    ("rest_mode_period", "Modo descanso"),
    ("vo2_max", "VO2 max"),
    ("tag", "Etiqueta"),
    ("enhanced_tag", "Etiqueta mejorada"),
    ("ring_configuration", "Configuración del anillo"),
    ("meal", "Comida"),
)

_EVENT_VALUES = {value for value, _label in WEBHOOK_EVENT_TYPES}
_DATA_VALUES = {value for value, _label in WEBHOOK_DATA_TYPES}


def is_known_event_type(value: str) -> bool:
    return value in _EVENT_VALUES


def is_known_data_type(value: str) -> bool:
    return value in _DATA_VALUES


def select_options(choices: tuple[tuple[str, str], ...], selected: str) -> str:
    parts: list[str] = []
    for value, label in choices:
        sel = " selected" if value == selected else ""
        parts.append(
            f'<option value="{escape(value, quote=True)}"{sel}>'
            f"{escape(label, quote=True)}</option>"
        )
    return "".join(parts)
