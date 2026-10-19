"""Tests for the buzzer buttons."""

from __future__ import annotations

from collections.abc import Callable
from unittest.mock import AsyncMock, MagicMock, call, patch

from bleak.exc import BleakError
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

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

from . import ADDRESS, NAME, TITLE, inject, service_info

ON = "button.sbbt_102c_ee01_start_buzzer"
OFF = "button.sbbt_102c_ee01_stop_buzzer"
BUZZ = "button.sbbt_102c_ee01_buzz"


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
        patch(
            "custom_components.bluetooth_button_plus.device.bluetooth.async_ble_device_from_address",
            return_value=None,
        ),
        pytest.raises(HomeAssistantError) as excinfo,
    ):
        await press(hass, ON)
    assert excinfo.value.translation_key == "not_in_range"
    assert excinfo.value.translation_placeholders == {"name": TITLE}
    connect.assert_not_awaited()


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (BleakError("le-connection-abort-by-local"), "cannot_connect"),
        (TimeoutError(), "cannot_connect"),
        (BleakError("Insufficient authentication"), "not_paired"),
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
    """The buttons follow the button coming into and going out of range."""
    unavailable_callbacks: list[Callable[..., None]] = []

    def _track(
        hass_: HomeAssistant, callback: Callable[..., None], *_: object, **__: object
    ) -> Callable[[], None]:
        unavailable_callbacks.append(callback)
        return lambda: None

    with patch(
        "custom_components.bluetooth_button_plus.entity.bluetooth.async_track_unavailable", _track
    ):
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        state = hass.states.get(ON)
        assert state is not None
        assert state.state == STATE_UNAVAILABLE

        inject(hass, service_info())
        await hass.async_block_till_done()
        state = hass.states.get(ON)
        assert state is not None
        assert state.state != STATE_UNAVAILABLE

        # Another advertisement changes nothing
        inject(hass, service_info())
        await hass.async_block_till_done()

        assert len(unavailable_callbacks) == 5
        with patch(
            "custom_components.bluetooth_button_plus.device.bluetooth.async_address_present",
            return_value=False,
        ):
            for callback in unavailable_callbacks:
                callback(service_info())
            await hass.async_block_till_done()
            state = hass.states.get(OFF)
            assert state is not None
            assert state.state == STATE_UNAVAILABLE

        assert await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()
        assert hass.states.get(ON) is None or hass.states.get(ON).state == STATE_UNAVAILABLE
