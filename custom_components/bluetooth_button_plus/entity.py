"""Base entities for Bluetooth Button Plus."""

from __future__ import annotations

from typing import Any

from homeassistant.components.bluetooth.passive_update_coordinator import (
    PassiveBluetoothCoordinatorEntity,
    PassiveBluetoothDataUpdateCoordinator,
)
from homeassistant.const import CONF_MODEL
from homeassistant.core import callback
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity import Entity

from . import BluButtonConfigEntry
from .const import DOMAIN
from .device import local_ble_device


class BluButtonDeviceEntity(Entity):
    """An entity of a Shelly BLU button whose value lives in Home Assistant."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry: BluButtonConfigEntry, key: str) -> None:
        """Initialize the entity."""
        self._entry = entry
        self._device = entry.runtime_data.button
        self._attr_unique_id = f"{self._device.address}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_BLUETOOTH, self._device.address)},
            identifiers={(DOMAIN, self._device.address)},
            name=entry.title,
            manufacturer="Shelly",
            model=entry.data.get(CONF_MODEL),
        )

    @callback
    def _async_save_option(self, key: str, value: Any) -> None:
        """Keep a configured value in the entry's options, for the next start."""
        self.hass.config_entries.async_update_entry(
            self._entry, options={**self._entry.options, key: value}
        )


class BluButtonEntity(
    PassiveBluetoothCoordinatorEntity[PassiveBluetoothDataUpdateCoordinator],
    BluButtonDeviceEntity,
):
    """An entity that needs the button in range of the host's own adapter.

    Available only while an adapter of the host sees the button: the bond
    lives there, so neither a Bluetooth proxy that only forwards
    advertisements nor one that can connect reaches the buzzer. Every
    advertisement, also one through a proxy, updates the availability.
    """

    def __init__(self, entry: BluButtonConfigEntry, key: str) -> None:
        """Initialize the entity."""
        PassiveBluetoothCoordinatorEntity.__init__(self, entry.runtime_data.coordinator)
        BluButtonDeviceEntity.__init__(self, entry, key)

    @property
    def available(self) -> bool:
        """Return whether the coordinator and an adapter of the host see the button."""
        return super().available and local_ble_device(self.hass, self._device.address) is not None
