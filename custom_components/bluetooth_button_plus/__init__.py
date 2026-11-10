"""Bluetooth Button Plus: the buzzer of Shelly BLU buttons as Home Assistant buttons."""

from __future__ import annotations

from dataclasses import dataclass
import logging

import probatio

from homeassistant.components.bluetooth import BluetoothScanningMode
from homeassistant.components.bluetooth.passive_update_coordinator import (
    PassiveBluetoothDataUpdateCoordinator,
)
from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.components.button.const import ButtonDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.typing import ConfigType, VolDictType

from .const import (
    ATTR_DURATION,
    ATTR_VOLUME,
    DEFAULT_BUZZ_SECONDS,
    DEFAULT_VOLUME,
    DOMAIN,
    MAX_BUZZ_SECONDS,
    MIN_BUZZ_SECONDS,
    OPTION_DURATION,
    OPTION_VOLUME,
    SERVICE_BUZZ,
    VOLUME_MAX,
    VOLUME_MIN,
)
from .device import BluButton

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.BUTTON, Platform.NUMBER]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

BUZZ_SCHEMA: VolDictType = {
    probatio.Optional(ATTR_DURATION): probatio.All(
        probatio.Coerce(float), probatio.Range(min=MIN_BUZZ_SECONDS, max=MAX_BUZZ_SECONDS)
    ),
    probatio.Optional(ATTR_VOLUME): probatio.All(
        probatio.Coerce(int), probatio.Range(min=VOLUME_MIN, max=VOLUME_MAX)
    ),
}


@dataclass(slots=True)
class RuntimeData:
    """What the entities of a button share."""

    button: BluButton
    # Tracks whether an adapter that can connect sees the button
    coordinator: PassiveBluetoothDataUpdateCoordinator


type BluButtonConfigEntry = ConfigEntry[RuntimeData]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the action "buzz", so it exists even while no button is loaded.

    Its target is the "Buzz" button (device class identify): a device as
    target buzzes once, not once per button.
    """
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_BUZZ,
        entity_domain=BUTTON_DOMAIN,
        schema=BUZZ_SCHEMA,
        func="async_buzz",
        entity_device_classes=[ButtonDeviceClass.IDENTIFY],
    )
    return True


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
        await entry.runtime_data.button.async_shutdown()
    return unloaded
