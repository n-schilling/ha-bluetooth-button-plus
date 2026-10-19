"""Tests for the buzzer buttons."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, call, patch

from bleak.exc import BleakDBusError, BleakError
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.components.bluetooth import BaseHaRemoteScanner
from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from custom_components.bluetooth_button_plus.const import (
    BUZZER_CHARACTERISTIC,
    BUZZER_OFF,
    BUZZER_ON,
    DEFAULT_VOLUME,
    DOMAIN,
    VOLUME_CHARACTERISTIC,
)

from . import ADDRESS, NAME, TITLE, ble_device, inject, service_info

ON = "button.sbbt_102c_ee01_start_buzzer"
OFF = "button.sbbt_102c_ee01_stop_buzzer"
BUZZ = "button.sbbt_102c_ee01_buzz"
VOLUME = "number.sbbt_102c_ee01_buzzer_volume"
DURATION = "number.sbbt_102c_ee01_buzz_duration"


async def press(hass: HomeAssistant, entity_id: str) -> None:
    """Press a button entity."""
    await hass.services.async_call(
        BUTTON_DOMAIN, SERVICE_PRESS, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )


async def test_entities_and_device(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Three buttons on one device that carries the Bluetooth address."""
    for entity_id, key in ((BUZZ, "buzz"), (ON, "buzzer_on"), (OFF, "buzzer_off")):
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state != STATE_UNAVAILABLE
        registry_entry = entity_registry.async_get(entity_id)
        assert registry_entry is not None
        assert registry_entry.unique_id == f"{ADDRESS}_{key}"
    device = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_BLUETOOTH, ADDRESS), entry.entry_id
    )
    assert device is not None
    assert device.name == TITLE
    assert device.manufacturer == "Shelly"
    assert device.model == NAME
    assert device.identifiers == {(DOMAIN, ADDRESS)}


async def test_press(
    hass: HomeAssistant, entry: MockConfigEntry, connect: AsyncMock, client: MagicMock
) -> None:
    """A press connects, writes 1 or 0 and disconnects."""
    await press(hass, ON)
    connect.assert_awaited_once()
    # One connection: the configured volume first, then the start
    assert client.write_gatt_char.await_args_list == [
        call(VOLUME_CHARACTERISTIC, bytes([DEFAULT_VOLUME]), response=True),
        call(BUZZER_CHARACTERISTIC, BUZZER_ON, response=True),
    ]
    client.disconnect.assert_awaited_once()
    # The retrying connection asks for the freshest device between attempts
    fresh = connect.await_args.kwargs["ble_device_callback"]()
    assert fresh.address == ADDRESS
    with patch(
        "custom_components.bluetooth_button_plus.device.bluetooth.async_ble_device_from_address",
        return_value=None,
    ):
        assert connect.await_args.kwargs["ble_device_callback"]().address == ADDRESS

    await press(hass, OFF)
    assert connect.await_count == 2
    client.write_gatt_char.assert_awaited_with(BUZZER_CHARACTERISTIC, BUZZER_OFF, response=True)
    assert client.disconnect.await_count == 2


async def test_press_out_of_range(
    hass: HomeAssistant, entry: MockConfigEntry, connect: AsyncMock
) -> None:
    """Without a connectable device the press fails and names the button."""
    with (
        patch("custom_components.bluetooth_button_plus.device._ble_device", return_value=None),
        pytest.raises(HomeAssistantError) as excinfo,
    ):
        await press(hass, ON)
    assert excinfo.value.translation_key == "not_in_range"
    assert excinfo.value.translation_placeholders == {"name": TITLE}
    connect.assert_not_awaited()


async def test_prefers_the_hosts_adapter(
    hass: HomeAssistant, entry: MockConfigEntry, connect: AsyncMock
) -> None:
    """The host's own adapter holds the bond, so it is used even when a proxy is closer."""
    remote = MagicMock()
    remote.scanner = MagicMock(spec=BaseHaRemoteScanner)
    remote.ble_device = ble_device(name="via proxy")
    remote.advertisement.rssi = -40
    local = MagicMock()
    local.scanner = MagicMock()
    local.ble_device = ble_device(name="via host")
    local.advertisement.rssi = -70
    with patch(
        "custom_components.bluetooth_button_plus.device.bluetooth.async_scanner_devices_by_address",
        return_value=[remote, local],
    ):
        await press(hass, ON)
    assert connect.await_args.args[1].name == "via host"

    # Only a proxy sees it: the last resort
    with patch(
        "custom_components.bluetooth_button_plus.device.bluetooth.async_scanner_devices_by_address",
        return_value=[remote],
    ):
        await press(hass, ON)
    assert connect.await_args.args[1].name == NAME


def _wrapped(cause: BaseException) -> BleakError:
    """An error as bleak-retry-connector raises it: the button's name in the text, the cause behind."""
    err = BleakError(f"Repair-Tag - {ADDRESS}: Failed to connect after 3 attempt(s): {cause}")
    err.__cause__ = cause
    return err


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (BleakError("le-connection-abort-by-local"), "cannot_connect"),
        (TimeoutError(), "cannot_connect"),
        (BleakError("Insufficient authentication"), "not_paired"),
        (BleakDBusError("org.bluez.Error.NotPermitted", []), "not_paired"),
        (
            BleakDBusError("org.bluez.Error.Failed", ["le-connection-abort-by-local"]),
            "cannot_connect",
        ),
        # The wrapper's text names the button ("Repair-Tag"), only the cause counts
        (_wrapped(BleakError("le-connection-abort-by-local")), "cannot_connect"),
        (_wrapped(BleakDBusError("org.bluez.Error.NotAuthorized", [])), "not_paired"),
    ],
)
async def test_press_cannot_connect(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    connect: AsyncMock,
    client: MagicMock,
    error: Exception,
    expected: str,
) -> None:
    """A failed connection raises a translated error."""
    connect.side_effect = error
    with pytest.raises(HomeAssistantError) as excinfo:
        await press(hass, ON)
    assert excinfo.value.translation_key == expected
    client.write_gatt_char.assert_not_awaited()


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (BleakError("Not permitted"), "not_paired"),
        (BleakDBusError("org.bluez.Error.NotPermitted", ["Write not permitted"]), "not_paired"),
        (BleakError("boom"), "write_failed"),
        (TimeoutError(), "write_failed"),
    ],
)
async def test_press_write_fails(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    client: MagicMock,
    error: Exception,
    expected: str,
) -> None:
    """A refused write raises a translated error and still disconnects."""
    client.write_gatt_char.side_effect = error
    with pytest.raises(HomeAssistantError) as excinfo:
        await press(hass, ON)
    assert excinfo.value.translation_key == expected
    client.disconnect.assert_awaited_once()


async def test_disconnect_errors_are_ignored(
    hass: HomeAssistant, entry: MockConfigEntry, client: MagicMock
) -> None:
    """A failing disconnect does not turn a successful press into an error."""
    client.disconnect.side_effect = BleakError("gone")
    await press(hass, ON)
    assert client.write_gatt_char.await_count == 2


async def test_availability(
    hass: HomeAssistant, bluetooth: None, connect: AsyncMock, config_entry: MockConfigEntry
) -> None:
    """The buttons follow the button coming into and going out of range; the duration stays."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    for entity_id in (ON, OFF, BUZZ, VOLUME):
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_UNAVAILABLE, entity_id
    state = hass.states.get(DURATION)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE

    inject(hass, service_info())
    await hass.async_block_till_done()
    for entity_id in (ON, OFF, BUZZ, VOLUME):
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state != STATE_UNAVAILABLE, entity_id

    # Home Assistant's Bluetooth manager reports the button gone
    config_entry.runtime_data.coordinator._async_handle_unavailable(service_info())
    await hass.async_block_till_done()
    for entity_id in (ON, OFF, BUZZ, VOLUME):
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_UNAVAILABLE, entity_id
    state = hass.states.get(DURATION)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    state = hass.states.get(ON)
    assert state is None or state.state == STATE_UNAVAILABLE
