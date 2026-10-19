"""Tests for Bluetooth Button Plus: helpers to feed Bluetooth advertisements."""

from __future__ import annotations

import time

from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_get_advertisement_callback,
)
from homeassistant.core import HomeAssistant

ADDRESS = "AA:BB:CC:DD:EE:01"
NAME = "SBBT-102C"
TITLE = "SBBT-102C EE01"
OTHER_ADDRESS = "AA:BB:CC:DD:EE:02"


def ble_device(address: str = ADDRESS, name: str = NAME) -> BLEDevice:
    """Return a bleak device."""
    return BLEDevice(address, name, {})


def service_info(
    address: str = ADDRESS, name: str = NAME, connectable: bool = True
) -> BluetoothServiceInfoBleak:
    """Return an advertisement of a Shelly BLU button as Home Assistant sees it."""
    # No manufacturer or service data on purpose: Shelly's manufacturer id and
    # the BTHome service data would start the discovery of those core
    # integrations, whose requirements the test harness does not install.
    advertisement = AdvertisementData(
        local_name=name,
        manufacturer_data={},
        service_data={},
        service_uuids=[],
        tx_power=-127,
        rssi=-60,
        platform_data=(),
    )
    return BluetoothServiceInfoBleak(
        name=name,
        address=address,
        rssi=-60,
        manufacturer_data={},
        service_data={},
        service_uuids=[],
        source="local",
        device=ble_device(address, name),
        advertisement=advertisement,
        connectable=connectable,
        time=time.monotonic(),
        tx_power=-127,
    )


def inject(hass: HomeAssistant, info: BluetoothServiceInfoBleak) -> None:
    """Hand an advertisement to Home Assistant's Bluetooth manager."""
    async_get_advertisement_callback(hass)(info)
