"""Buttons: start and stop the buzzer."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BluButtonConfigEntry
from .entity import BluButtonEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BluButtonConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the buttons."""
    async_add_entities([BuzzerOnButton(entry), BuzzerOffButton(entry)])


class BuzzerOnButton(BluButtonEntity, ButtonEntity):
    """Start the buzzer; it stops by itself after a minute."""

    def __init__(self, entry: BluButtonConfigEntry) -> None:
        """Initialize the button."""
        super().__init__(entry, "buzzer_on")

    async def async_press(self) -> None:
        """Start the buzzer."""
        await self._device.async_set_buzzer(True)


class BuzzerOffButton(BluButtonEntity, ButtonEntity):
    """Stop the buzzer."""

    def __init__(self, entry: BluButtonConfigEntry) -> None:
        """Initialize the button."""
        super().__init__(entry, "buzzer_off")

    async def async_press(self) -> None:
        """Stop the buzzer."""
        await self._device.async_set_buzzer(False)
