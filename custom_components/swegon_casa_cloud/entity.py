"""Shared Swegon CASA entity helpers."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SwegonCasaCoordinator


class SwegonCasaEntity(CoordinatorEntity[SwegonCasaCoordinator]):
    """Base entity tied to the configured CASA unit."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SwegonCasaCoordinator) -> None:
        super().__init__(coordinator)
        thing = coordinator.data["summary"]["thing"]
        self._thing_id = str(thing["id"])
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._thing_id)},
            manufacturer="Swegon",
            model=str(thing.get("ahuName") or "CASA"),
            name=str(thing.get("nickname") or thing.get("ahuName") or "Swegon CASA"),
            sw_version=str(thing.get("ahuSwVersion") or thing.get("swVersion") or ""),
        )
