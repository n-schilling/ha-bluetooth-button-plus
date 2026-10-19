"""Numbers: the buzzer volume and the buzz duration."""

from __future__ import annotations

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BluButtonConfigEntry
from .const import (
    MAX_BUZZ_SECONDS,
    MIN_BUZZ_SECONDS,
    OPTION_DURATION,
    OPTION_VOLUME,
    VOLUME_MAX,
    VOLUME_MIN,
)
from .entity import BluButtonDeviceEntity, BluButtonEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BluButtonConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the numbers."""
    async_add_entities([BuzzerVolumeNumber(entry), BuzzDurationNumber(entry)])


class BuzzerVolumeNumber(BluButtonEntity, NumberEntity):
    """The volume the buzzer starts with: 0 off, 1 low, 2 medium, 3 high.

    The button cannot be asked for its volume without a connection, so the
    entity shows the value Home Assistant set last, kept in the entry's
    options; every start of the buzzer writes it to the button first.
    """

    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.SLIDER
    _attr_native_min_value = VOLUME_MIN
    _attr_native_max_value = VOLUME_MAX
    _attr_native_step = 1

    def __init__(self, entry: BluButtonConfigEntry) -> None:
        """Initialize the number."""
        super().__init__(entry, "volume")

    @property
    def native_value(self) -> float:
        """Return the configured volume."""
        return float(self._device.volume)

    async def async_set_native_value(self, value: float) -> None:
        """Write the volume to the button and keep it."""
        await self._device.async_set_volume(int(value))
        self._async_save_option(OPTION_VOLUME, int(value))
        self.async_write_ha_state()


class BuzzDurationNumber(BluButtonDeviceEntity, NumberEntity):
    """The seconds a buzz lasts: for the button "Buzz" and the action without a duration.

    Kept in Home Assistant only; the button has no setting for it, so it can
    be set while the button is away.
    """

    _attr_entity_category = EntityCategory.CONFIG
    _attr_device_class = NumberDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = MIN_BUZZ_SECONDS
    _attr_native_max_value = MAX_BUZZ_SECONDS
    _attr_native_step = 1

    def __init__(self, entry: BluButtonConfigEntry) -> None:
        """Initialize the number."""
        super().__init__(entry, "duration")

    @property
    def native_value(self) -> float:
        """Return the configured duration."""
        return self._device.duration

    async def async_set_native_value(self, value: float) -> None:
        """Keep the duration."""
        self._device.duration = value
        self._async_save_option(OPTION_DURATION, value)
        self.async_write_ha_state()
