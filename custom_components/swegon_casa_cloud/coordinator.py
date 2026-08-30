"""Coordinator for Swegon CASA cloud mode control."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import SwegonCasaApi, SwegonCasaError
from .const import (
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    MODE_TO_WRITE_VALUE,
)
from .mqtt import SwegonCasaMqttError, read_status, write_mode

_LOGGER = logging.getLogger(__name__)


class SwegonCasaCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Keep the cloud summary and current operating mode fresh."""

    def __init__(self, hass: HomeAssistant, api: SwegonCasaApi, thing_id: str) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=DEFAULT_UPDATE_INTERVAL,
        )
        self.api = api
        self.thing_id = thing_id

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            summary = await self.api.async_summary(self.thing_id)
            status = await self.hass.async_add_executor_job(read_status, summary)
        except (SwegonCasaError, SwegonCasaMqttError) as error:
            raise UpdateFailed("Unable to update Swegon CASA") from error
        return {"summary": summary, **status}

    async def async_set_mode(self, mode: str) -> None:
        """Set one allow-listed ventilation mode and verify the unit accepted it."""
        if mode not in MODE_TO_WRITE_VALUE:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="unsupported_mode",
                translation_placeholders={"mode": mode},
            )
        try:
            summary = await self.api.async_summary(self.thing_id)
            await self.hass.async_add_executor_job(
                write_mode,
                summary,
                MODE_TO_WRITE_VALUE[mode],
            )
        except (SwegonCasaError, SwegonCasaMqttError) as error:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_mode_failed",
            ) from error
        self.async_set_updated_data(
            {**self.data, "summary": summary, "mode": MODE_TO_WRITE_VALUE[mode]}
        )
