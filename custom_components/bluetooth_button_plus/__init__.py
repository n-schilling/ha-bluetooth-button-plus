"""Bluetooth Button Plus: the buzzer of Shelly BLU buttons as Home Assistant buttons."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from homeassistant.components.bluetooth import BluetoothScanningMode
from homeassistant.components.bluetooth.passive_update_coordinator import (
    PassiveBluetoothDataUpdateCoordinator,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant

from .const import DEFAULT_BUZZ_SECONDS, DEFAULT_VOLUME, OPTION_DURATION, OPTION_VOLUME
from .device import BluButton

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.BUTTON, Platform.NUMBER]


@dataclass(slots=True)
class RuntimeData:
    """What the entities of a button share."""

    button: BluButton
    # Tracks whether an adapter that can connect sees the button
    coordinator: PassiveBluetoothDataUpdateCoordinator


type BluButtonConfigEntry = ConfigEntry[RuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: BluButtonConfigEntry) -> bool:
    """Set up a button.

    The setup does not need the button in range: a button that is away makes
    its entities unavailable, it does not block the entry.
    """
    address: str = entry.data[CONF_ADDRESS]
    button = BluButton(
        hass,
        address,
        entry.title,
        entry.options.get(OPTION_VOLUME, DEFAULT_VOLUME),
        entry.options.get(OPTION_DURATION, DEFAULT_BUZZ_SECONDS),
    )
    coordinator = PassiveBluetoothDataUpdateCoordinator(
        hass, _LOGGER, address, BluetoothScanningMode.PASSIVE, connectable=True
    )
    entry.runtime_data = RuntimeData(button, coordinator)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(coordinator.async_start())
    return True


async def async_unload_entry(hass: HomeAssistant, entry: BluButtonConfigEntry) -> bool:
    """Unload a button."""
    if unloaded := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        entry.runtime_data.button.async_shutdown()
    return unloaded
