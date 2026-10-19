"""Tests for the buzzer volume."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, call

from bleak.exc import BleakError
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.number import ATTR_VALUE, DOMAIN as NUMBER_DOMAIN, SERVICE_SET_VALUE
from homeassistant.const import ATTR_ENTITY_ID, CONF_ADDRESS, CONF_MODEL, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from custom_components.bluetooth_button_plus.const import (
    BUZZER_CHARACTERISTIC,
    BUZZER_ON,
    DOMAIN,
    OPTION_DURATION,
    OPTION_VOLUME,
    VOLUME_CHARACTERISTIC,
)

from . import ADDRESS, NAME, TITLE, inject, service_info

VOLUME = "number.sbbt_102c_ee01_buzzer_volume"
DURATION = "number.sbbt_102c_ee01_buzz_duration"
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


async def test_out_of_range(
    hass: HomeAssistant, bluetooth: None, connect: AsyncMock, config_entry: MockConfigEntry
) -> None:
    """Out of range the volume cannot be set; the duration lives in Home Assistant and can."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    state = hass.states.get(VOLUME)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    state = hass.states.get(DURATION)
    assert state is not None
    assert float(state.state) == 10
    assert state.attributes["unit_of_measurement"] == "s"
    assert state.attributes["device_class"] == "duration"
    assert state.attributes["min"] == 1
    assert state.attributes["max"] == 60
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: DURATION, ATTR_VALUE: 42},
        blocking=True,
    )
    state = hass.states.get(DURATION)
    assert state is not None
    assert float(state.state) == 42
    connect.assert_not_awaited()


async def test_options_survive(hass: HomeAssistant, bluetooth: None, connect: AsyncMock) -> None:
    """Volume and duration come from the entry's options and go back there when set."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title=TITLE,
        unique_id=ADDRESS,
        data={CONF_ADDRESS: ADDRESS, CONF_MODEL: NAME},
        options={OPTION_VOLUME: 2, OPTION_DURATION: 7},
    )
    inject(hass, service_info())
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    state = hass.states.get(VOLUME)
    assert state is not None
    assert state.state == "2.0"
    state = hass.states.get(DURATION)
    assert state is not None
    assert float(state.state) == 7
    connect.assert_not_awaited()

    await set_volume(hass, 3)
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: DURATION, ATTR_VALUE: 42},
        blocking=True,
    )
    assert config_entry.options == {OPTION_VOLUME: 3, OPTION_DURATION: 42.0}
    assert config_entry.runtime_data.button.volume == 3
    assert config_entry.runtime_data.button.duration == 42.0
