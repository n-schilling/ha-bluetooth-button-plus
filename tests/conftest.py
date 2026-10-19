"""Fixtures: Home Assistant's Bluetooth stack without hardware, a button simulated in memory."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.const import CONF_ADDRESS, CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from custom_components.bluetooth_button_plus.const import DOMAIN

from . import ADDRESS, NAME, TITLE, inject, service_info


@pytest.fixture(autouse=True)
def _custom_integrations(enable_custom_integrations: None) -> None:
    """Load the integration from custom_components."""


@pytest.fixture
async def bluetooth(hass: HomeAssistant, mock_bluetooth: None) -> None:
    """Set up the Bluetooth integration with a simulated adapter."""
    assert await async_setup_component(hass, "bluetooth", {})
    await hass.async_block_till_done()


@pytest.fixture
def client() -> MagicMock:
    """A connected bleak client of a button with a buzzer."""
    client = MagicMock()
    client.services.get_characteristic.return_value = object()
    client.write_gatt_char = AsyncMock()
    client.disconnect = AsyncMock()
    return client


@pytest.fixture
def connect(client: MagicMock) -> Generator[AsyncMock]:
    """The connection to the button, answering with the client."""
    with patch(
        "custom_components.bluetooth_button_plus.device.establish_connection",
        AsyncMock(return_value=client),
    ) as mock:
        yield mock


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """A config entry of the button, not yet added."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=TITLE,
        unique_id=ADDRESS,
        data={CONF_ADDRESS: ADDRESS, CONF_MODEL: NAME},
    )


@pytest.fixture
async def entry(
    hass: HomeAssistant, bluetooth: None, connect: AsyncMock, config_entry: MockConfigEntry
) -> AsyncGenerator[MockConfigEntry]:
    """The button set up, in range of the adapter."""
    inject(hass, service_info())
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    yield config_entry
    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
