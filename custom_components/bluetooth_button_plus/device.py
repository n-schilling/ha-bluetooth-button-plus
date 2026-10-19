"""The Bluetooth connection to a Shelly BLU button."""

from __future__ import annotations

import asyncio
import contextlib
from datetime import datetime
from functools import partial
import logging

from bleak.backends.device import BLEDevice
from bleak.exc import BleakDBusError, BleakError
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import BaseHaRemoteScanner
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_call_later

from .const import (
    BUZZER_CHARACTERISTIC,
    BUZZER_OFF,
    BUZZER_ON,
    DOMAIN,
    MAX_CONNECT_ATTEMPTS,
    VOLUME_CHARACTERISTIC,
)

_LOGGER = logging.getLogger(__name__)

# Both characteristics a button needs; the setup refuses a device without them
REQUIRED_CHARACTERISTICS = (BUZZER_CHARACTERISTIC, VOLUME_CHARACTERISTIC)

# BlueZ answers these when a bonded connection is required but missing
_AUTH_DBUS_ERRORS = frozenset(
    {
        "org.bluez.Error.NotPermitted",
        "org.bluez.Error.NotAuthorized",
        "org.bluez.Error.AuthenticationFailed",
        "org.bluez.Error.AuthenticationRejected",
        "org.bluez.Error.AuthenticationCanceled",
    }
)
# Other backends say it in words; checked on the original error only
_AUTH_WORDS = ("authentication", "not permitted", "not authorized", "encrypt")

type Write = tuple[str, bytes]


class CannotConnect(Exception):
    """The button is not reachable or refuses the connection."""


class NotPaired(Exception):
    """The button refuses the access because it is not paired with the adapter."""


class NotSupported(Exception):
    """The device answered, but lacks the buzzer or the volume characteristic."""


def _is_auth_error(err: BaseException) -> bool:
    """Return whether the button refused the access for want of a bond.

    Follows the causes down to the original error: bleak-retry-connector wraps
    it in a message that carries the button's name, which must not be searched.
    """
    current = err
    seen: set[int] = set()
    while True:
        if isinstance(current, BleakDBusError):
            return current.dbus_error in _AUTH_DBUS_ERRORS
        cause = current.__cause__
        if cause is None or id(cause) in seen:
            text = str(current).lower()
            return any(word in text for word in _AUTH_WORDS)
        seen.add(id(current))
        current = cause


def _ble_device(hass: HomeAssistant, address: str) -> BLEDevice | None:
    """Return the button as the host's own adapter sees it, or as any adapter does.

    The bond lives in the host's Bluetooth stack, so its adapter is the one
    that can write; a proxy is the last resort.
    """
    devices = bluetooth.async_scanner_devices_by_address(hass, address, connectable=True)
    local = [device for device in devices if not isinstance(device.scanner, BaseHaRemoteScanner)]
    if local:
        return max(local, key=lambda device: device.advertisement.rssi or -127).ble_device
    return bluetooth.async_ble_device_from_address(hass, address, True)


async def _async_connect(
    hass: HomeAssistant, ble_device: BLEDevice, name: str
) -> BleakClientWithServiceCache:
    """Connect to the button, with the retries Bluetooth needs."""

    def _fresh_device() -> BLEDevice:
        return _ble_device(hass, ble_device.address) or ble_device

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
    """Connect once and check that the device has the buzzer and the volume.

    A button that is not paired with the adapter refuses the connection while
    its services are read, so this also checks the pairing.
    """
    client = await _async_connect(hass, ble_device, name)
    try:
        for characteristic in REQUIRED_CHARACTERISTICS:
            if client.services.get_characteristic(characteristic) is None:
                raise NotSupported
    finally:
        await _async_disconnect(client)


class BluButton:
    """A Shelly BLU button, addressed by its Bluetooth address.

    Every command takes the lock, so a start, a stop, a volume and a timed stop
    never interleave. A generation counter tells a timed stop whether a newer
    command has overtaken it while it waited for the lock.
    """

    def __init__(
        self, hass: HomeAssistant, address: str, name: str, volume: int, duration: float
    ) -> None:
        """Initialize the button with the configured volume and buzz duration."""
        self.hass = hass
        self.address = address
        self.name = name
        self.volume = volume
        self.duration = duration
        self._lock = asyncio.Lock()
        self._generation = 0
        self._stop_timer: CALLBACK_TYPE | None = None

    async def async_start_buzzer(self, volume: int | None = None) -> None:
        """Start the buzzer at the volume, or at the configured one; the button stops it."""
        async with self._lock:
            self._async_supersede()
            await self._async_write(*self._start_writes(volume))

    async def async_stop_buzzer(self) -> None:
        """Stop the buzzer, and a timed stop that is still pending."""
        async with self._lock:
            self._async_supersede()
            await self._async_write((BUZZER_CHARACTERISTIC, BUZZER_OFF))

    async def async_set_volume(self, volume: int) -> None:
        """Write the volume to the button and keep it as the configured one."""
        async with self._lock:
            await self._async_write((VOLUME_CHARACTERISTIC, bytes([volume])))
            self.volume = volume

    async def async_buzz(self, duration: float | None = None, volume: int | None = None) -> None:
        """Start the buzzer and stop it after the duration in seconds.

        Without a duration or a volume the configured ones are used. The stop
        runs in the background: the call returns once the buzzer started. A
        new buzz replaces a pending stop.
        """
        async with self._lock:
            generation = self._async_supersede()
            await self._async_write(*self._start_writes(volume))
            self._stop_timer = async_call_later(
                self.hass,
                self.duration if duration is None else duration,
                partial(self._async_timed_stop, generation),
            )

    async def _async_timed_stop(self, generation: int, _now: datetime) -> None:
        async with self._lock:
            if generation != self._generation:
                # A newer command came first while this stop waited for the lock
                return
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
    def _async_supersede(self) -> int:
        """Drop a pending timed stop and start a new generation; call with the lock held."""
        if self._stop_timer is not None:
            self._stop_timer()
            self._stop_timer = None
        self._generation += 1
        return self._generation

    @callback
    def async_shutdown(self) -> None:
        """Drop a pending timed stop; the button stops by itself after a minute."""
        self._async_supersede()

    def _start_writes(self, volume: int | None) -> tuple[Write, Write]:
        level = self.volume if volume is None else volume
        return (VOLUME_CHARACTERISTIC, bytes([level])), (BUZZER_CHARACTERISTIC, BUZZER_ON)

    async def _async_write(self, *writes: Write) -> None:
        """Connect, write the values in order and disconnect; call with the lock held.

        One connection per command, closed right after the writes: the button
        is a battery device and advertises only while nothing is connected.
        """
        ble_device = _ble_device(self.hass, self.address)
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
