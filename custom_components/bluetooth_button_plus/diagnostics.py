"""Diagnostics: who sees the button, and the state of its commands.

Without the Bluetooth address, the title (it ends in part of the address),
the discovery keys and the names of the scanners: the entry is described by
its model and settings, a scanner by its kind only.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import BaseHaRemoteScanner
from homeassistant.const import CONF_MODEL
from homeassistant.core import HomeAssistant

from . import BluButtonConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: BluButtonConfigEntry
) -> dict[str, Any]:
    """Return the diagnostics of a button."""
    button = entry.runtime_data.button
    coordinator = entry.runtime_data.coordinator
    seen_by = [
        {
            "host_adapter": not isinstance(device.scanner, BaseHaRemoteScanner),
            "connectable": device.scanner.connectable,
            "rssi": device.advertisement.rssi,
        }
        for device in bluetooth.async_scanner_devices_by_address(
            hass, button.address, connectable=False
        )
    ]
    return {
        "model": entry.data.get(CONF_MODEL),
        "coordinator_available": coordinator.available,
        "in_range": button.in_range,
        "seen_by": sorted(seen_by, key=lambda scanner: scanner["rssi"] or -127, reverse=True),
        "volume": button.volume,
        "duration": button.duration,
        "busy": button.busy,
        "stop_pending": button.stop_pending,
    }
