"""Read-only Swegon CASA summer-cooling activity sensor."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity

from . import SwegonCasaConfigEntry
from .const import summer_mode_is_active
from .coordinator import SwegonCasaCoordinator
from .entity import SwegonCasaEntity


async def async_setup_entry(
    _hass: Any,
    entry: SwegonCasaConfigEntry,
    async_add_entities: Any,
) -> None:
    """Set up summer-cooling activity."""
    async_add_entities(
        [SwegonCasaSummerCoolingActive(entry.runtime_data.coordinator)]
    )


class SwegonCasaSummerCoolingActive(SwegonCasaEntity, BinarySensorEntity):
    """Report whether summer cooling is currently affecting the unit."""

    _attr_translation_key = "summer_cooling_active"
    _attr_icon = "mdi:snowflake-thermometer"

    def __init__(self, coordinator: SwegonCasaCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._thing_id}_summer_cooling_active"

    @property
    def is_on(self) -> bool | None:
        """Return true while the app's Summer mode boost card is active."""
        return summer_mode_is_active(
            self.coordinator.data["summer_mode_boost"],
            self.coordinator.data["summer_mode_state"],
            self.coordinator.data["mode"],
            self.coordinator.data["application"],
        )
