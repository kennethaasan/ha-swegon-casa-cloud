"""Config flow for Swegon CASA cloud."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    SwegonCasaApi,
    SwegonCasaAuthenticationError,
    SwegonCasaError,
)
from .const import (
    CONF_APP_API_KEY,
    CONF_REFRESH_TOKEN,
    CONF_THING_ID,
    DOMAIN,
)


class SwegonCasaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure an authenticated Swegon CASA mobile-app session."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate private mobile credentials and select the first unit."""
        errors: dict[str, str] = {}
        if user_input is not None:
            api = SwegonCasaApi(
                async_get_clientsession(self.hass),
                user_input[CONF_APP_API_KEY],
                user_input[CONF_REFRESH_TOKEN],
            )
            try:
                things = await api.async_validate()
            except SwegonCasaAuthenticationError:
                errors["base"] = "invalid_auth"
            except SwegonCasaError:
                errors["base"] = "cannot_connect"
            else:
                if not things:
                    errors["base"] = "no_units"
                else:
                    thing = things[0]
                    thing_id = str(thing["id"])
                    await self.async_set_unique_id(thing_id)
                    self._abort_if_unique_id_configured()
                    title = str(
                        thing.get("nickname")
                        or thing.get("ahuName")
                        or "Swegon CASA"
                    )
                    return self.async_create_entry(
                        title=title,
                        data={
                            CONF_APP_API_KEY: user_input[CONF_APP_API_KEY],
                            CONF_REFRESH_TOKEN: api.refresh_token,
                            CONF_THING_ID: thing_id,
                        },
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_APP_API_KEY): str,
                    vol.Required(CONF_REFRESH_TOKEN): str,
                }
            ),
            errors=errors,
        )
