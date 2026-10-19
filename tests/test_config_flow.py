"""Tests for the config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from bleak.exc import BleakError
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import SOURCE_BLUETOOTH, SOURCE_USER
from homeassistant.const import CONF_ADDRESS, CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.bluetooth_button_plus.const import BUZZER_CHARACTERISTIC, DOMAIN

from . import ADDRESS, NAME, OTHER_ADDRESS, TITLE, inject, service_info


async def test_discovery(
    hass: HomeAssistant, bluetooth: None, connect: AsyncMock, client: MagicMock
) -> None:
    """A discovered button is confirmed; the setup connects once to check it."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=service_info()
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert result["description_placeholders"] == {"name": TITLE, "address": ADDRESS}
    assert hass.config_entries.flow.async_get(result["flow_id"])["context"][
        "title_placeholders"
    ] == {"name": TITLE}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TITLE
    assert result["data"] == {CONF_ADDRESS: ADDRESS, CONF_MODEL: NAME}
    assert result["result"].unique_id == ADDRESS
    connect.assert_awaited_once()
    client.services.get_characteristic.assert_called_once_with(BUZZER_CHARACTERISTIC)
    client.disconnect.assert_awaited_once()


async def test_discovery_of_another_device(hass: HomeAssistant, bluetooth: None) -> None:
    """A Shelly BLU device that is no button is refused."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=service_info(name="SBDW-002C")
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_supported"


async def test_discovery_already_configured(
    hass: HomeAssistant, bluetooth: None, config_entry: MockConfigEntry
) -> None:
    """A configured button is not offered again."""
    config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=service_info()
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (BleakError("le-connection-abort-by-local"), "cannot_connect"),
        (TimeoutError(), "cannot_connect"),
        (BleakError("Insufficient authentication"), "not_paired"),
    ],
)
async def test_discovery_connection_errors(
    hass: HomeAssistant, bluetooth: None, connect: AsyncMock, error: Exception, expected: str
) -> None:
    """A failed check shows the error and lets the user try again."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=service_info()
    )
    connect.side_effect = error
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert result["errors"] == {"base": expected}

    connect.side_effect = None
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_discovery_without_buzzer(
    hass: HomeAssistant, bluetooth: None, connect: AsyncMock, client: MagicMock
) -> None:
    """A device without the buzzer characteristic is refused after the check."""
    client.services.get_characteristic.return_value = None
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=service_info()
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_supported"
    client.disconnect.assert_awaited_once()


async def test_user_flow(hass: HomeAssistant, bluetooth: None, connect: AsyncMock) -> None:
    """The user picks a button from those an adapter sees."""
    inject(hass, service_info())
    inject(hass, service_info(address=OTHER_ADDRESS, name="SBDW-002C"))
    inject(hass, service_info(address="AA:BB:CC:DD:EE:03", connectable=False))
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    schema = result["data_schema"]
    assert schema is not None
    choices = schema.schema[CONF_ADDRESS].container
    assert choices == {ADDRESS: f"{TITLE} ({ADDRESS})"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ADDRESS: ADDRESS}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TITLE
    assert result["data"] == {CONF_ADDRESS: ADDRESS, CONF_MODEL: NAME}
    connect.assert_awaited_once()


async def test_user_flow_error_then_success(
    hass: HomeAssistant, bluetooth: None, connect: AsyncMock
) -> None:
    """A failed check keeps the form with the chosen button."""
    inject(hass, service_info())
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    connect.side_effect = BleakError("not permitted")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ADDRESS: ADDRESS}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "not_paired"}

    connect.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ADDRESS: ADDRESS}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_without_buttons(hass: HomeAssistant, bluetooth: None) -> None:
    """Without a button in range there is nothing to pick."""
    inject(hass, service_info(name="SBDW-002C"))
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_user_flow_skips_configured(
    hass: HomeAssistant, bluetooth: None, config_entry: MockConfigEntry
) -> None:
    """A configured button is not offered again."""
    config_entry.add_to_hass(hass)
    inject(hass, service_info())
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"
