"""Buttons: buzz for the configured time, start and stop the buzzer; the action "buzz"."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import probatio

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
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
from .device import BluButton
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


@dataclass(frozen=True, kw_only=True)
class BluButtonButtonDescription(ButtonEntityDescription):
    """A button and what a press does."""

    press_fn: Callable[[BluButton], Awaitable[None]]


BUTTONS: tuple[BluButtonButtonDescription, ...] = (
    # "Buzz" is the target of the action "buzz" (device class identify), so a
    # device as target buzzes once, not once per button
    BluButtonButtonDescription(
        key="buzz",
        translation_key="buzz",
        device_class=ButtonDeviceClass.IDENTIFY,
        press_fn=lambda button: button.async_buzz(),
    ),
    BluButtonButtonDescription(
        key="buzzer_on",
        translation_key="buzzer_on",
        press_fn=lambda button: button.async_start_buzzer(),
    ),
    BluButtonButtonDescription(
        key="buzzer_off",
        translation_key="buzzer_off",
        press_fn=lambda button: button.async_stop_buzzer(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BluButtonConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the buttons and the action "buzz"."""
    entity_platform.async_get_current_platform().async_register_entity_service(
        SERVICE_BUZZ,
        BUZZ_SCHEMA,
        "async_buzz",
        entity_device_classes=[ButtonDeviceClass.IDENTIFY],
    )
    async_add_entities(BluButtonButton(entry, description) for description in BUTTONS)


class BluButtonButton(BluButtonEntity, ButtonEntity):
    """A button of the Shelly BLU button."""

    entity_description: BluButtonButtonDescription

    def __init__(
        self, entry: BluButtonConfigEntry, description: BluButtonButtonDescription
    ) -> None:
        """Initialize the button."""
        super().__init__(entry, description.key)
        self.entity_description = description

    async def async_press(self) -> None:
        """Do what the button is for."""
        await self.entity_description.press_fn(self._device)

    async def async_buzz(self, duration: float | None = None, volume: int | None = None) -> None:
        """Buzz for the duration at the volume (the action "buzz")."""
        await self._device.async_buzz(duration, volume)
