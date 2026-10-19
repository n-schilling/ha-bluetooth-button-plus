"""Tests for the buzzer volume."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, call

from bleak.exc import BleakError
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    mock_restore_cache_with_extra_data,
)

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.number import ATTR_VALUE, DOMAIN as NUMBER_DOMAIN, SERVICE_SET_VALUE
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component

from custom_components.bluetooth_button_plus.const import (
    BUZZER_CHARACTERISTIC,
    BUZZER_ON,
    VOLUME_CHARACTERISTIC,
)

from . import inject, service_info

VOLUME = "number.sbbt_102c_ee01_buzzer_volume"
ON = "button.sbbt_102c_ee01_start_buzzer"


async def set_volume(hass: HomeAssistant, value: int) -> None:
    """Set the volume entity."""
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: VOLUME, ATTR_VALUE: value},
        blocking=True,
    )


async def test_volume(
    hass: HomeAssistant, entry: MockConfigEntry, connect: AsyncMock, client: MagicMock
) -> None:
    """The volume starts at the button's factory setting and is written when set."""
    state = hass.states.get(VOLUME)
    assert state is not None
    assert state.state == "1.0"
    assert state.attributes["min"] == 0
    assert state.attributes["max"] == 3
    assert state.attributes["step"] == 1

    await set_volume(hass, 3)
    connect.assert_awaited_once()
    client.write_gatt_char.assert_awaited_once_with(VOLUME_CHARACTERISTIC, b"\x03", response=True)
    client.disconnect.assert_awaited_once()
    state = hass.states.get(VOLUME)
    assert state is not None
    assert state.state == "3.0"

    # The buzzer starts at the new volume from now on
    client.write_gatt_char.reset_mock()
    await hass.services.async_call(
        BUTTON_DOMAIN, SERVICE_PRESS, {ATTR_ENTITY_ID: ON}, blocking=True
    )
    assert client.write_gatt_char.await_args_list == [
        call(VOLUME_CHARACTERISTIC, b"\x03", response=True),
        call(BUZZER_CHARACTERISTIC, BUZZER_ON, response=True),
    ]


async def test_volume_write_fails(
    hass: HomeAssistant, entry: MockConfigEntry, client: MagicMock
) -> None:
    """A refused write keeps the old volume."""
    client.write_gatt_char.side_effect = BleakError("boom")
    with pytest.raises(HomeAssistantError) as excinfo:
        await set_volume(hass, 2)
    assert excinfo.value.translation_key == "write_failed"
    state = hass.states.get(VOLUME)
    assert state is not None
    assert state.state == "1.0"


async def test_volume_restored(
    hass: HomeAssistant, bluetooth: None, connect: AsyncMock, config_entry: MockConfigEntry
) -> None:
    """After a restart the volume set before is used again, without a connection."""
    # RestoreNumber stores the value under native_value
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(VOLUME, "2.0"),
                {
                    "native_max_value": 3,
                    "native_min_value": 0,
                    "native_step": 1,
                    "native_unit_of_measurement": None,
                    "native_value": 2.0,
                },
            )
        ],
    )
    inject(hass, service_info())
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    state = hass.states.get(VOLUME)
    assert state is not None
    assert state.state == "2.0"
    connect.assert_not_awaited()


async def test_volume_unavailable_out_of_range(
    hass: HomeAssistant, bluetooth: None, connect: AsyncMock, config_entry: MockConfigEntry
) -> None:
    """Out of range the volume cannot be set."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    state = hass.states.get(VOLUME)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_translations_load(hass: HomeAssistant) -> None:
    """The translation files are valid and complete for the entities and the action."""
    assert await async_setup_component(hass, "homeassistant", {})
