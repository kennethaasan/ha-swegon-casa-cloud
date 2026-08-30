"""Ventilation-mode selector for Swegon CASA."""

from __future__ import annotations

from typing import Any

from homeassistant.components.select import SelectEntity
from . import SwegonCasaConfigEntry
from .const import CONTROL_VALUE_TO_MODE, MODE_TO_WRITE_VALUE
from .coordinator import SwegonCasaCoordinator
from .entity import SwegonCasaEntity


async def async_setup_entry(
    _hass: Any,
    entry: SwegonCasaConfigEntry,
    async_add_entities: Any,
) -> None:
    """Set up the Swegon CASA mode selector."""
    async_add_entities([SwegonCasaModeSelect(entry.runtime_data.coordinator)])


class SwegonCasaModeSelect(SwegonCasaEntity, SelectEntity):
    """Allow-list the safe operating modes exposed by the official app."""

    _attr_has_entity_name = True
    _attr_translation_key = "ventilation_mode"
    _attr_icon = "mdi:air-filter"
    def __init__(self, coordinator: SwegonCasaCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._thing_id}_ventilation_mode"

    @property
    def current_option(self) -> str | None:
        """Return the current allow-listed mode."""
        return CONTROL_VALUE_TO_MODE.get(self.coordinator.data["mode"])

    @property
    def options(self) -> list[str]:
        """Include read-only transient states only while they are active."""
        current = self.current_option
        writable = list(MODE_TO_WRITE_VALUE)
        if current is not None and current not in writable:
            return [current, *writable]
        return writable

    async def async_select_option(self, option: str) -> None:
        """Set and verify a Swegon operating mode."""
        await self.coordinator.async_set_mode(option)
