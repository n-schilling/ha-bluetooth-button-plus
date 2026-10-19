"""The Bluetooth connection to a Shelly BLU button."""

from __future__ import annotations

import asyncio
import contextlib
import logging

from bleak.backends.device import BLEDevice
from bleak.exc import BleakError
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import BUZZER_CHARACTERISTIC, BUZZER_OFF, BUZZER_ON, DOMAIN, MAX_CONNECT_ATTEMPTS

_LOGGER = logging.getLogger(__name__)

# Words BlueZ and bleak use when a bonded connection is required but missing
_AUTH_ERRORS = ("auth", "not permitted", "encrypt", "bond", "pair")


class CannotConnect(Exception):
    """The button is not reachable or refuses the connection."""


class NotPaired(Exception):
    """The button refuses the access because it is not paired with the adapter."""


class NotSupported(Exception):
    """The device answered, but has no buzzer characteristic."""


def _is_auth_error(err: Exception) -> bool:
    text = str(err).lower()
    return any(word in text for word in _AUTH_ERRORS)


async def _async_connect(
    hass: HomeAssistant, ble_device: BLEDevice, name: str
) -> BleakClientWithServiceCache:
    """Connect to the button, with the retries Bluetooth needs."""

    def _fresh_device() -> BLEDevice:
        return bluetooth.async_ble_device_from_address(hass, ble_device.address, True) or ble_device

    try:
        return await establish_connection(
            BleakClientWithServiceCache,
            ble_device,
            name,
            max_attempts=MAX_CONNECT_ATTEMPTS,
            ble_device_callback=_fresh_device,
        )
    except (BleakError, TimeoutError) as err:
        if _is_auth_error(err):
            raise NotPaired from err
        raise CannotConnect from err


async def _async_disconnect(client: BleakClientWithServiceCache) -> None:
    with contextlib.suppress(BleakError, TimeoutError):
        await client.disconnect()


async def async_check_button(hass: HomeAssistant, ble_device: BLEDevice, name: str) -> None:
    """Connect once and check that the device has the buzzer characteristic.

    A button that is not paired with the adapter refuses the connection while
    its services are read, so this also checks the pairing.
    """
    client = await _async_connect(hass, ble_device, name)
    try:
        if client.services.get_characteristic(BUZZER_CHARACTERISTIC) is None:
            raise NotSupported
    finally:
        await _async_disconnect(client)


class BluButton:
    """A Shelly BLU button, addressed by its Bluetooth address."""

    def __init__(self, hass: HomeAssistant, address: str, name: str) -> None:
        """Initialize the button."""
        self.hass = hass
        self.address = address
        self.name = name
        self._lock = asyncio.Lock()

    @property
    def present(self) -> bool:
        """Return whether an adapter that can connect currently sees the button."""
        return bluetooth.async_address_present(self.hass, self.address, connectable=True)

    async def async_set_buzzer(self, on: bool) -> None:
        """Start or stop the buzzer.

        One connection per press, closed right after the write: the button is
        a battery device and keeps advertising only while nothing is connected.
        """
        async with self._lock:
            ble_device = bluetooth.async_ble_device_from_address(self.hass, self.address, True)
            if ble_device is None:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="not_in_range",
                    translation_placeholders={"name": self.name},
                )
            try:
                client = await _async_connect(self.hass, ble_device, self.name)
            except NotPaired as err:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="not_paired",
                    translation_placeholders={"name": self.name},
                ) from err
            except CannotConnect as err:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="cannot_connect",
                    translation_placeholders={"name": self.name, "error": str(err.__cause__)},
                ) from err
            try:
                await client.write_gatt_char(
                    BUZZER_CHARACTERISTIC, BUZZER_ON if on else BUZZER_OFF, response=True
                )
            except (BleakError, TimeoutError) as err:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="not_paired" if _is_auth_error(err) else "write_failed",
                    translation_placeholders={"name": self.name, "error": str(err)},
                ) from err
            finally:
                await _async_disconnect(client)
            _LOGGER.debug("%s: buzzer %s", self.name, "on" if on else "off")
