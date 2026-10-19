"""Base entity for Bluetooth Button Plus."""

from __future__ import annotations

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import (
    BluetoothCallbackMatcher,
    BluetoothChange,
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
)
from homeassistant.const import CONF_MODEL
from homeassistant.core import callback
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity import Entity

from . import BluButtonConfigEntry
from .const import DOMAIN


class BluButtonEntity(Entity):
    """An entity of a Shelly BLU button.

    Available only while an adapter that can connect sees the button: the
    buzzer cannot be reached through a scanner that only forwards
    advertisements, such as a Shelly Bluetooth proxy.
    """

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry: BluButtonConfigEntry, key: str) -> None:
        """Initialize the entity."""
        self._device = entry.runtime_data
        self._attr_unique_id = f"{self._device.address}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_BLUETOOTH, self._device.address)},
            identifiers={(DOMAIN, self._device.address)},
            name=entry.title,
            manufacturer="Shelly",
            model=entry.data.get(CONF_MODEL),
        )
        self._was_available = self._device.present

    @property
    def available(self) -> bool:
        """Return whether the button is in range of an adapter that can connect."""
        return self._device.present

    async def async_added_to_hass(self) -> None:
        """Follow the button coming into and going out of range."""
        await super().async_added_to_hass()
        self.async_on_remove(
            bluetooth.async_register_callback(
                self.hass,
                self._async_seen,
                BluetoothCallbackMatcher(address=self._device.address, connectable=True),
                BluetoothScanningMode.PASSIVE,
            )
        )
        self.async_on_remove(
            bluetooth.async_track_unavailable(
                self.hass, self._async_unavailable, self._device.address, connectable=True
            )
        )

    @callback
    def _async_seen(self, service_info: BluetoothServiceInfoBleak, change: BluetoothChange) -> None:
        self._async_availability_changed()

    @callback
    def _async_unavailable(self, service_info: BluetoothServiceInfoBleak) -> None:
        self._async_availability_changed()

    @callback
    def _async_availability_changed(self) -> None:
        """Write the state only when the availability flips, not on every advertisement."""
        available = self.available
        if available != self._was_available:
            self._was_available = available
            self.async_write_ha_state()
