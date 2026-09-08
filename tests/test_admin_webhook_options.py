from __future__ import annotations

from oura_mcp_server.admin.webhook_options import (
    WEBHOOK_DATA_TYPES,
    WEBHOOK_EVENT_TYPES,
    is_known_data_type,
    is_known_event_type,
    select_options,
)


def test_event_types_oficiales() -> None:
    assert is_known_event_type("create")
    assert is_known_event_type("update")
    assert is_known_event_type("delete")
    assert not is_known_event_type("upsert")


def test_data_types_oficiales() -> None:
    assert is_known_data_type("daily_sleep")
    assert is_known_data_type("vo2_max")
    assert is_known_data_type("meal")
    assert not is_known_data_type("spo2Daily")


def test_select_options_marca_el_seleccionado() -> None:
    html = select_options(WEBHOOK_EVENT_TYPES, "update")
    assert 'value="update" selected>' in html
    assert 'value="create"' in html
    assert "selected>" in html
    assert html.count(" selected") == 1
    assert len(WEBHOOK_DATA_TYPES) >= 10
