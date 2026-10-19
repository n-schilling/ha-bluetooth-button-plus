"""Tests for the action "buzz"."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from unittest.mock import AsyncMock, MagicMock, call

from bleak.exc import BleakError
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.number import ATTR_VALUE, DOMAIN as NUMBER_DOMAIN, SERVICE_SET_VALUE
from homeassistant.const import ATTR_DEVICE_ID, ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceNotSupported
from homeassistant.helpers import device_registry as dr
from homeassistant.util import dt as dt_util

from custom_components.bluetooth_button_plus.const import (
    ATTR_DURATION,
    ATTR_VOLUME,
    BUZZER_CHARACTERISTIC,
    BUZZER_OFF,
    BUZZER_ON,
    DOMAIN,
    SERVICE_BUZZ,
    VOLUME_CHARACTERISTIC,
)

from . import ADDRESS

BUZZ = "button.sbbt_102c_ee01_buzz"
ON = "button.sbbt_102c_ee01_start_buzzer"
OFF = "button.sbbt_102c_ee01_stop_buzzer"
DURATION = "number.sbbt_102c_ee01_buzz_duration"


async def buzz(hass: HomeAssistant, target: dict[str, str], **data: float) -> None:
    """Call the action."""
    await hass.services.async_call(DOMAIN, SERVICE_BUZZ, {**target, **data}, blocking=True)


async def elapse(hass: HomeAssistant, seconds: float) -> None:
    """Fire the timers due within the seconds from now (not from the last call)."""
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=seconds))
    await hass.async_block_till_done()


async def test_buzz(
    hass: HomeAssistant, entry: MockConfigEntry, connect: AsyncMock, client: MagicMock
) -> None:
    """The buzzer starts at once and stops after the duration."""
    await buzz(hass, {ATTR_ENTITY_ID: BUZZ}, **{ATTR_DURATION: 5, ATTR_VOLUME: 2})
    connect.assert_awaited_once()
    assert client.write_gatt_char.await_args_list == [
        call(VOLUME_CHARACTERISTIC, b"\x02", response=True),
        call(BUZZER_CHARACTERISTIC, BUZZER_ON, response=True),
    ]

    await elapse(hass, 4)
    assert connect.await_count == 1

    await elapse(hass, 6)
    assert connect.await_count == 2
    client.write_gatt_char.assert_awaited_with(BUZZER_CHARACTERISTIC, BUZZER_OFF, response=True)
    assert client.disconnect.await_count == 2


async def test_buzz_defaults(
    hass: HomeAssistant, entry: MockConfigEntry, connect: AsyncMock, client: MagicMock
) -> None:
    """Without fields: ten seconds at the configured volume."""
    await buzz(hass, {ATTR_ENTITY_ID: BUZZ})
    assert client.write_gatt_char.await_args_list[0] == call(
        VOLUME_CHARACTERISTIC, b"\x01", response=True
    )
    await elapse(hass, 9)
    assert connect.await_count == 1
    await elapse(hass, 11)
    assert connect.await_count == 2


async def test_buzz_targets_the_device_once(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    connect: AsyncMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """A device as target buzzes once; the stop button is left out."""
    device = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_BLUETOOTH, ADDRESS), entry.entry_id
    )
    assert device is not None
    await buzz(hass, {ATTR_DEVICE_ID: device.id}, **{ATTR_DURATION: 1})
    connect.assert_awaited_once()


@pytest.mark.parametrize("entity_id", [ON, OFF])
async def test_buzz_refuses_the_other_buttons(
    hass: HomeAssistant, entry: MockConfigEntry, entity_id: str
) -> None:
    """Start and stop named directly are no targets for the action."""
    with pytest.raises(ServiceNotSupported):
        await buzz(hass, {ATTR_ENTITY_ID: entity_id}, **{ATTR_DURATION: 1})


async def test_buzz_button(
    hass: HomeAssistant, entry: MockConfigEntry, connect: AsyncMock, client: MagicMock
) -> None:
    """The button "Buzz" buzzes for the configured duration at the configured volume."""
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: DURATION, ATTR_VALUE: 3},
        blocking=True,
    )
    connect.assert_not_awaited()
    state = hass.states.get(DURATION)
    assert state is not None
    assert float(state.state) == 3

    await hass.services.async_call(
        BUTTON_DOMAIN, SERVICE_PRESS, {ATTR_ENTITY_ID: BUZZ}, blocking=True
    )
    connect.assert_awaited_once()
    assert client.write_gatt_char.await_args_list == [
        call(VOLUME_CHARACTERISTIC, b"\x01", response=True),
        call(BUZZER_CHARACTERISTIC, BUZZER_ON, response=True),
    ]
    await elapse(hass, 2)
    assert connect.await_count == 1
    await elapse(hass, 4)
    assert connect.await_count == 2
    client.write_gatt_char.assert_awaited_with(BUZZER_CHARACTERISTIC, BUZZER_OFF, response=True)

    # The action without a duration uses the configured one as well
    await buzz(hass, {ATTR_ENTITY_ID: BUZZ})
    assert connect.await_count == 3
    await elapse(hass, 2)
    assert connect.await_count == 3
    await elapse(hass, 4)
    assert connect.await_count == 4


async def test_stop_cancels_the_timed_stop(
    hass: HomeAssistant, entry: MockConfigEntry, connect: AsyncMock
) -> None:
    """Pressing stop ends a buzz early and drops the pending stop."""
    await buzz(hass, {ATTR_ENTITY_ID: BUZZ}, **{ATTR_DURATION: 30})
    await hass.services.async_call(
        BUTTON_DOMAIN, SERVICE_PRESS, {ATTR_ENTITY_ID: OFF}, blocking=True
    )
    assert connect.await_count == 2
    await elapse(hass, 31)
    assert connect.await_count == 2


async def test_new_buzz_replaces_the_timed_stop(
    hass: HomeAssistant, entry: MockConfigEntry, connect: AsyncMock
) -> None:
    """A second buzz restarts the time; only the later stop runs."""
    await buzz(hass, {ATTR_ENTITY_ID: BUZZ}, **{ATTR_DURATION: 5})
    await elapse(hass, 3)
    await buzz(hass, {ATTR_ENTITY_ID: BUZZ}, **{ATTR_DURATION: 8})
    assert connect.await_count == 2
    # The first stop (due at 5 s) was dropped
    await elapse(hass, 6)
    assert connect.await_count == 2
    await elapse(hass, 9)
    assert connect.await_count == 3


async def test_timed_stop_failure_is_logged(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    connect: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A stop that fails after the time is a warning, not an error: the button stops itself."""
    await buzz(hass, {ATTR_ENTITY_ID: BUZZ}, **{ATTR_DURATION: 2})
    connect.side_effect = BleakError("le-connection-abort-by-local")
    with caplog.at_level(logging.WARNING):
        await elapse(hass, 3)
    assert "could not be stopped after the time" in caplog.text


async def test_unload_drops_the_timed_stop(
    hass: HomeAssistant, entry: MockConfigEntry, connect: AsyncMock
) -> None:
    """Unloading the entry cancels a pending stop."""
    await buzz(hass, {ATTR_ENTITY_ID: BUZZ}, **{ATTR_DURATION: 5})
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    await elapse(hass, 6)
    assert connect.await_count == 1


async def test_timed_stop_overtaken_by_a_new_buzz(
    hass: HomeAssistant, entry: MockConfigEntry, connect: AsyncMock, client: MagicMock
) -> None:
    """A stop that falls due while a new buzz is being written does not cut the new buzz."""
    gate = asyncio.Event()
    gate.set()
    entered = asyncio.Event()

    async def write(*_args: object, **_kwargs: object) -> None:
        entered.set()
        await gate.wait()

    client.write_gatt_char = AsyncMock(side_effect=write)
    await buzz(hass, {ATTR_ENTITY_ID: BUZZ}, **{ATTR_DURATION: 5})

    # The second buzz holds the lock while its write hangs
    gate.clear()
    entered.clear()
    second = hass.async_create_task(entry.runtime_data.button.async_buzz(5))
    await entered.wait()
    # The first stop falls due and waits for the lock
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=6))
    await asyncio.sleep(0)
    gate.set()
    await second
    await hass.async_block_till_done()
    assert not any(call.args[1] == BUZZER_OFF for call in client.write_gatt_char.await_args_list), (
        "the overtaken stop wrote OFF"
    )

    # The second buzz keeps its own stop
    await elapse(hass, 12)
    assert client.write_gatt_char.await_args_list[-1].args[1] == BUZZER_OFF
    assert sum(1 for c in client.write_gatt_char.await_args_list if c.args[1] == BUZZER_OFF) == 1


async def test_stop_pressed_while_a_buzz_starts(
    hass: HomeAssistant, entry: MockConfigEntry, connect: AsyncMock, client: MagicMock
) -> None:
    """Stop pressed during a hanging start wins: the buzz's stop is dropped, OFF is written once."""
    gate = asyncio.Event()
    entered = asyncio.Event()

    async def write(*_args: object, **_kwargs: object) -> None:
        entered.set()
        await gate.wait()

    client.write_gatt_char = AsyncMock(side_effect=write)
    first = hass.async_create_task(entry.runtime_data.button.async_buzz(5))
    await entered.wait()
    stop = hass.async_create_task(entry.runtime_data.button.async_stop_buzzer())
    await asyncio.sleep(0)
    gate.set()
    await first
    await stop
    await hass.async_block_till_done()
    assert client.write_gatt_char.await_args_list[-1].args[1] == BUZZER_OFF
    await elapse(hass, 6)
    assert sum(1 for c in client.write_gatt_char.await_args_list if c.args[1] == BUZZER_OFF) == 1


async def test_stop_task_overtaken_by_a_queued_buzz(
    hass: HomeAssistant, entry: MockConfigEntry, connect: AsyncMock, client: MagicMock
) -> None:
    """A stop queued behind a new buzz at the lock finds a newer generation and steps aside.

    A volume write holds the lock; a new buzz queues up behind it; then the
    first buzz's stop falls due and queues up behind the new buzz.
    """
    gate = asyncio.Event()
    gate.set()
    entered = asyncio.Event()

    async def write(*_args: object, **_kwargs: object) -> None:
        entered.set()
        await gate.wait()

    client.write_gatt_char = AsyncMock(side_effect=write)
    button = entry.runtime_data.button
    await buzz(hass, {ATTR_ENTITY_ID: BUZZ}, **{ATTR_DURATION: 5})

    gate.clear()
    entered.clear()
    holder = hass.async_create_task(button.async_set_volume(2))
    await entered.wait()
    second = hass.async_create_task(button.async_buzz(5))
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=6))
    await asyncio.sleep(0)
    gate.set()
    await holder
    await second
    await hass.async_block_till_done()
    assert not any(call.args[1] == BUZZER_OFF for call in client.write_gatt_char.await_args_list)
    assert connect.await_count == 3

    await elapse(hass, 12)
    assert client.write_gatt_char.await_args_list[-1].args[1] == BUZZER_OFF
    assert connect.await_count == 4
