"""Number: the buzzer volume."""

from __future__ import annotations

from homeassistant.components.number import NumberMode, RestoreNumber
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BluButtonConfigEntry
from .const import VOLUME_MAX, VOLUME_MIN
from .entity import BluButtonEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BluButtonConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the volume."""
    async_add_entities([BuzzerVolumeNumber(entry)])


class BuzzerVolumeNumber(BluButtonEntity, RestoreNumber):
    """The volume the buzzer starts with: 0 off, 1 low, 2 medium, 3 high.

    The button cannot be asked for its volume without a connection, so the
    entity holds the value Home Assistant set last and restores it after a
    restart; every start of the buzzer writes it to the button first.
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

    async def async_added_to_hass(self) -> None:
        """Restore the volume set before the restart."""
        await super().async_added_to_hass()
        last = await self.async_get_last_number_data()
        if last is not None and last.native_value is not None:
            self._device.volume = int(last.native_value)

    async def async_set_native_value(self, value: float) -> None:
        """Write the volume to the button."""
        await self._device.async_set_volume(int(value))
        self.async_write_ha_state()
