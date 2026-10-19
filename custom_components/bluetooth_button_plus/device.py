"""The Bluetooth connection to a Shelly BLU button."""

from __future__ import annotations

import asyncio
import contextlib
from datetime import datetime
import logging

from bleak.backends.device import BLEDevice
from bleak.exc import BleakError
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection

from homeassistant.components import bluetooth
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_call_later

from .const import (
    BUZZER_CHARACTERISTIC,
    BUZZER_OFF,
    BUZZER_ON,
    DEFAULT_VOLUME,
    DOMAIN,
    MAX_CONNECT_ATTEMPTS,
    VOLUME_CHARACTERISTIC,
)

_LOGGER = logging.getLogger(__name__)

# Words BlueZ and bleak use when a bonded connection is required but missing
_AUTH_ERRORS = ("auth", "not permitted", "encrypt", "bond", "pair")

type Write = tuple[str, bytes]


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
        # The volume the buzzer starts with; the number entity restores and sets it
        self.volume: int = DEFAULT_VOLUME
        self._lock = asyncio.Lock()
        self._stop_timer: CALLBACK_TYPE | None = None

    @property
    def present(self) -> bool:
        """Return whether an adapter that can connect currently sees the button."""
        return bluetooth.async_address_present(self.hass, self.address, connectable=True)

    async def async_start_buzzer(self, volume: int | None = None) -> None:
        """Start the buzzer at the volume, or at the configured one."""
        level = self.volume if volume is None else volume
        await self._async_write(
            (VOLUME_CHARACTERISTIC, bytes([level])), (BUZZER_CHARACTERISTIC, BUZZER_ON)
        )

    async def async_stop_buzzer(self) -> None:
        """Stop the buzzer, and a timed stop that is still pending."""
        self._cancel_timed_stop()
        await self._async_write((BUZZER_CHARACTERISTIC, BUZZER_OFF))

    async def async_set_volume(self, volume: int) -> None:
        """Write the volume to the button and keep it as the configured one."""
        await self._async_write((VOLUME_CHARACTERISTIC, bytes([volume])))
        self.volume = volume

    async def async_buzz(self, duration: float, volume: int | None = None) -> None:
        """Start the buzzer and stop it after the duration in seconds.

        The stop runs in the background: the call returns once the buzzer
        started. A new buzz replaces a pending stop.
        """
        await self.async_start_buzzer(volume)
        self._cancel_timed_stop()
        self._stop_timer = async_call_later(self.hass, duration, self._async_timed_stop)

    async def _async_timed_stop(self, _now: datetime) -> None:
        self._stop_timer = None
        try:
            await self._async_write((BUZZER_CHARACTERISTIC, BUZZER_OFF))
        except HomeAssistantError as err:
            _LOGGER.warning(
                "%s: the buzzer could not be stopped after the time, "
                "it stops by itself after a minute: %s",
                self.name,
                err,
            )

    @callback
    def _cancel_timed_stop(self) -> None:
        if self._stop_timer is not None:
            self._stop_timer()
            self._stop_timer = None

    @callback
    def async_shutdown(self) -> None:
        """Drop a pending timed stop; the button stops by itself after a minute."""
        self._cancel_timed_stop()

    async def _async_write(self, *writes: Write) -> None:
        """Connect, write the values in order and disconnect.

        One connection per command, closed right after the writes: the button
        is a battery device and advertises only while nothing is connected.
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
                for characteristic, value in writes:
                    await client.write_gatt_char(characteristic, value, response=True)
            except (BleakError, TimeoutError) as err:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="not_paired" if _is_auth_error(err) else "write_failed",
                    translation_placeholders={"name": self.name, "error": str(err)},
                ) from err
            finally:
                await _async_disconnect(client)
            _LOGGER.debug("%s: wrote %s", self.name, [c[-4:] + "=" + v.hex() for c, v in writes])
