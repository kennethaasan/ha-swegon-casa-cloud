"""Read-only Swegon CASA summer-cooling sensors."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import PERCENTAGE

from . import SwegonCasaConfigEntry
from .const import (
    CONTROL_SOURCE,
    SUMMER_MODE_SETTING,
)
from .coordinator import SwegonCasaCoordinator
from .entity import SwegonCasaEntity


async def async_setup_entry(
    _hass: Any,
    entry: SwegonCasaConfigEntry,
    async_add_entities: Any,
) -> None:
    """Set up summer-cooling status sensors."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        [
            SwegonCasaMappedSensor(
                coordinator,
                key="summer_mode_setting",
                unique_id_suffix="summer_mode_detection",
                translation_key="summer_mode_setting",
                icon="mdi:weather-sunny",
                value_map=SUMMER_MODE_SETTING,
            ),
            SwegonCasaNumericSensor(
                coordinator,
                key="summer_mode_boost",
                translation_key="summer_mode_boost_level",
                icon="mdi:fan-auto",
                native_unit=PERCENTAGE,
            ),
            SwegonCasaMappedSensor(
                coordinator,
                key="control_source",
                unique_id_suffix="heating_state",
                translation_key="ventilation_control_source",
                icon="mdi:swap-horizontal",
                value_map=CONTROL_SOURCE,
            ),
        ]
    )


class SwegonCasaMappedSensor(SwegonCasaEntity, SensorEntity):
    """Map a bounded Swegon register value to a descriptive state."""

    def __init__(
        self,
        coordinator: SwegonCasaCoordinator,
        *,
        key: str,
        unique_id_suffix: str | None = None,
        translation_key: str,
        icon: str,
        value_map: dict[int, str],
    ) -> None:
        super().__init__(coordinator)
        self._key = key
        self._value_map = value_map
        self._attr_translation_key = translation_key
        self._attr_icon = icon
        self._attr_unique_id = f"{self._thing_id}_{unique_id_suffix or key}"

    @property
    def native_value(self) -> str | None:
        """Return the mapped register state."""
        value = self.coordinator.data[self._key]
        if value is None:
            return None
        return self._value_map.get(value, f"Unknown ({value})")


class SwegonCasaNumericSensor(SwegonCasaEntity, SensorEntity):
    """Expose one numeric app register without reinterpreting its value."""

    def __init__(
        self,
        coordinator: SwegonCasaCoordinator,
        *,
        key: str,
        translation_key: str,
        icon: str,
        native_unit: str,
    ) -> None:
        super().__init__(coordinator)
        self._key = key
        self._attr_translation_key = translation_key
        self._attr_icon = icon
        self._attr_native_unit_of_measurement = native_unit
        self._attr_unique_id = f"{self._thing_id}_{key}"

    @property
    def native_value(self) -> int | None:
        """Return the raw bounded percentage used by the official app."""
        return self.coordinator.data[self._key]
