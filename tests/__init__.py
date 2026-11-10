"""Tests for Bluetooth Button Plus: helpers to feed Bluetooth advertisements."""

from __future__ import annotations

import time

from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from pytest_homeassistant.components.bluetooth import FakeScanner

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_get_advertisement_callback,
)
from homeassistant.core import HomeAssistant

ADDRESS = "AA:BB:CC:DD:EE:01"
NAME = "SBBT-102C"
TITLE = "SBBT-102C EE01"
OTHER_ADDRESS = "AA:BB:CC:DD:EE:02"

# The source of the host's own adapter in these tests
LOCAL_SOURCE = "local"
LOCAL_SCANNER = "bluetooth_button_plus_test_local_scanner"


class LocalScanner(FakeScanner):
    """The host's own adapter: it reports what it saw, as a real adapter does."""

    def __init__(self) -> None:
        """Initialize the scanner as a connectable local adapter."""
        super().__init__(LOCAL_SOURCE, "hci0", connectable=True)
        self.seen: dict[str, tuple[BLEDevice, AdvertisementData]] = {}

    @property
    def discovered_devices(self) -> list[BLEDevice]:
        """Return the devices the adapter saw."""
        return [device for device, _ in self.seen.values()]

    @property
    def discovered_devices_and_advertisement_data(
        self,
    ) -> dict[str, tuple[BLEDevice, AdvertisementData]]:
        """Return the devices the adapter saw, with their last advertisement."""
        return self.seen


def ble_device(address: str = ADDRESS, name: str = NAME) -> BLEDevice:
    """Return a bleak device."""
    return BLEDevice(address, name, {})


def service_info(
    address: str = ADDRESS,
    name: str = NAME,
    connectable: bool = True,
    source: str = LOCAL_SOURCE,
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
        source=source,
        device=ble_device(address, name),
        advertisement=advertisement,
        connectable=connectable,
        time=time.monotonic(),
        tx_power=-127,
    )


def inject(hass: HomeAssistant, info: BluetoothServiceInfoBleak) -> None:
    """Hand an advertisement to Home Assistant's Bluetooth manager.

    An advertisement from the local source counts as seen by the host's
    adapter as well, so the integration can connect through it.
    """
    scanner: LocalScanner | None = hass.data.get(LOCAL_SCANNER)
    if scanner is not None and info.source == LOCAL_SOURCE and info.connectable:
        scanner.seen[info.address] = (info.device, info.advertisement)
    async_get_advertisement_callback(hass)(info)


def see_locally(hass: HomeAssistant, info: BluetoothServiceInfoBleak) -> None:
    """Let the host's adapter see the button without announcing it (no discovery flow)."""
    hass.data[LOCAL_SCANNER].seen[info.address] = (info.device, info.advertisement)


def forget(hass: HomeAssistant, address: str = ADDRESS) -> None:
    """Let the host's adapter lose the button; other scanners may still see it."""
    hass.data[LOCAL_SCANNER].seen.pop(address, None)
