"""Swegon CASA cloud integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SwegonCasaApi
from .const import (
    CONF_APP_API_KEY,
    CONF_REFRESH_TOKEN,
    CONF_THING_ID,
    PLATFORMS,
)
from .coordinator import SwegonCasaCoordinator


@dataclass
class SwegonCasaRuntimeData:
    """Runtime objects shared by Swegon platforms."""

    api: SwegonCasaApi
    coordinator: SwegonCasaCoordinator


SwegonCasaConfigEntry = ConfigEntry[SwegonCasaRuntimeData]


async def async_setup_entry(
    hass: HomeAssistant, entry: SwegonCasaConfigEntry
) -> bool:
    """Set up Swegon CASA from a config entry."""

    def refresh_token_updated(refresh_token: str) -> None:
        hass.config_entries.async_update_entry(
            entry,
            data={**entry.data, CONF_REFRESH_TOKEN: refresh_token},
        )

    api = SwegonCasaApi(
        async_get_clientsession(hass),
        entry.data[CONF_APP_API_KEY],
        entry.data[CONF_REFRESH_TOKEN],
        refresh_token_updated,
    )
    coordinator = SwegonCasaCoordinator(hass, api, entry.data[CONF_THING_ID])
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = SwegonCasaRuntimeData(api, coordinator)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: SwegonCasaConfigEntry
) -> bool:
    """Unload a Swegon CASA config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
