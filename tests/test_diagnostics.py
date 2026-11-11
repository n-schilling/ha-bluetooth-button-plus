"""Tests for the diagnostics and for logging a button that goes out of range."""

from __future__ import annotations

import json
import logging

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from custom_components.bluetooth_button_plus.const import DEFAULT_BUZZ_SECONDS, DEFAULT_VOLUME

from . import ADDRESS, NAME, TITLE, forget, see_locally, service_info


async def test_diagnostics(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, entry: MockConfigEntry
) -> None:
    """The diagnostics say who sees the button, without its address or title."""
    assert await async_setup_component(hass, "diagnostics", {})
    data = await get_diagnostics_for_config_entry(hass, hass_client, entry)
    assert data == {
        "model": NAME,
        "coordinator_available": True,
        "in_range": True,
        "seen_by": [{"host_adapter": True, "connectable": True, "rssi": -60}],
        "volume": DEFAULT_VOLUME,
        "duration": DEFAULT_BUZZ_SECONDS,
        "busy": False,
        "stop_pending": False,
    }
    text = json.dumps(data)
    assert ADDRESS not in text
    assert ADDRESS.replace(":", "") not in text
    assert TITLE not in text


async def test_logs_range_once(
    hass: HomeAssistant, entry: MockConfigEntry, caplog: pytest.LogCaptureFixture
) -> None:
    """Going out of range is logged once, coming back once."""
    caplog.set_level(logging.INFO, logger="custom_components.bluetooth_button_plus")
    coordinator = entry.runtime_data.coordinator
    forget(hass)
    coordinator.async_update_listeners()
    coordinator.async_update_listeners()
    assert caplog.text.count("is out of range") == 1
    assert entry.runtime_data.button.in_range is False

    see_locally(hass, service_info())
    coordinator.async_update_listeners()
    coordinator.async_update_listeners()
    assert caplog.text.count("is back in range") == 1
    assert entry.runtime_data.button.in_range is True
