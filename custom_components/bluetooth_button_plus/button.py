"""Buttons: buzz for the configured time, start and stop the buzzer; the action "buzz"."""

from __future__ import annotations

import probatio

from homeassistant.components.button import ButtonEntity
from homeassistant.components.button.const import ButtonDeviceClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import VolDictType

from . import BluButtonConfigEntry
from .const import (
    ATTR_DURATION,
    ATTR_VOLUME,
    MAX_BUZZ_SECONDS,
    MIN_BUZZ_SECONDS,
    SERVICE_BUZZ,
    VOLUME_MAX,
    VOLUME_MIN,
)
from .entity import BluButtonEntity

PARALLEL_UPDATES = 1

BUZZ_SCHEMA: VolDictType = {
    probatio.Optional(ATTR_DURATION): probatio.All(
        probatio.Coerce(float), probatio.Range(min=MIN_BUZZ_SECONDS, max=MAX_BUZZ_SECONDS)
    ),
    probatio.Optional(ATTR_VOLUME): probatio.All(
        probatio.Coerce(int), probatio.Range(min=VOLUME_MIN, max=VOLUME_MAX)
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BluButtonConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the buttons and the action "buzz"."""
    # The action targets the "Buzz" button only (device class identify), so a
    # device as target buzzes once, not once per button
    entity_platform.async_get_current_platform().async_register_entity_service(
        SERVICE_BUZZ,
        BUZZ_SCHEMA,
        "async_buzz",
        entity_device_classes=[ButtonDeviceClass.IDENTIFY],
    )
    async_add_entities([BuzzButton(entry), BuzzerOnButton(entry), BuzzerOffButton(entry)])


class BuzzButton(BluButtonEntity, ButtonEntity):
    """Buzz for the configured time at the configured volume."""

    _attr_device_class = ButtonDeviceClass.IDENTIFY

    def __init__(self, entry: BluButtonConfigEntry) -> None:
        """Initialize the button."""
        super().__init__(entry, "buzz")

    async def async_press(self) -> None:
        """Buzz for the configured time."""
        await self._device.async_buzz()

    async def async_buzz(self, duration: float | None = None, volume: int | None = None) -> None:
        """Buzz for the duration at the volume (the action "buzz")."""
        await self._device.async_buzz(duration, volume)


class BuzzerOnButton(BluButtonEntity, ButtonEntity):
    """Start the buzzer at the configured volume; it stops by itself after a minute."""

    def __init__(self, entry: BluButtonConfigEntry) -> None:
        """Initialize the button."""
        super().__init__(entry, "buzzer_on")

    async def async_press(self) -> None:
        """Start the buzzer."""
        await self._device.async_start_buzzer()


class BuzzerOffButton(BluButtonEntity, ButtonEntity):
    """Stop the buzzer."""

    def __init__(self, entry: BluButtonConfigEntry) -> None:
        """Initialize the button."""
        super().__init__(entry, "buzzer_off")

    async def async_press(self) -> None:
        """Stop the buzzer."""
        await self._device.async_stop_buzzer()
