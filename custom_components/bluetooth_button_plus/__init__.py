"""Bluetooth Button Plus: the buzzer of Shelly BLU buttons as Home Assistant buttons."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant

from .device import BluButton

PLATFORMS: list[Platform] = [Platform.BUTTON, Platform.NUMBER]

type BluButtonConfigEntry = ConfigEntry[BluButton]


async def async_setup_entry(hass: HomeAssistant, entry: BluButtonConfigEntry) -> bool:
    """Set up a button.

    The setup does not need the button in range: a button that is away makes
    its entities unavailable, it does not block the entry.
    """
    entry.runtime_data = BluButton(hass, entry.data[CONF_ADDRESS], entry.title)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: BluButtonConfigEntry) -> bool:
    """Unload a button."""
    if unloaded := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        entry.runtime_data.async_shutdown()
    return unloaded
