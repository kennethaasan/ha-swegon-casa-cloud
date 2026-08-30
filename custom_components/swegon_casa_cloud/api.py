"""Authenticated Swegon CASA mobile API client."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from aiohttp import ClientError, ClientSession

from .const import API_BASE_URL, APP_USER_AGENT


class SwegonCasaError(Exception):
    """Base Swegon CASA client error."""


class SwegonCasaAuthenticationError(SwegonCasaError):
    """Swegon CASA rejected the stored credentials."""


class SwegonCasaApi:
    """Small client for the endpoints used by the official mobile app."""

    def __init__(
        self,
        session: ClientSession,
        app_api_key: str,
        refresh_token: str,
        refresh_token_updated: Callable[[str], None] | None = None,
    ) -> None:
        self._session = session
        self._app_api_key = app_api_key
        self._refresh_token = refresh_token
        self._refresh_token_updated = refresh_token_updated
        self._access_token: str | None = None
        self._access_token_expires_at = datetime.min.replace(tzinfo=UTC)
        self._refresh_lock = asyncio.Lock()

    @property
    def refresh_token(self) -> str:
        """Return the latest rotated refresh token."""
        return self._refresh_token

    async def async_validate(self) -> list[dict[str, Any]]:
        """Validate the refresh token and return the account's units."""
        await self._async_refresh_access_token(force=True)
        return await self.async_list_things()

    async def async_list_things(self) -> list[dict[str, Any]]:
        """Return all ventilation units associated with the account."""
        response = await self._async_request("GET", "/mobile/thing")
        if not isinstance(response, list):
            raise SwegonCasaError("Unexpected Swegon unit response")
        return [item for item in response if isinstance(item, dict)]

    async def async_summary(self, thing_id: str) -> dict[str, Any]:
        """Return fresh dashboard and MQTT connection details for a unit."""
        response = await self._async_request(
            "GET", f"/mobile/thing/{thing_id}/summary?language=en"
        )
        if not isinstance(response, dict):
            raise SwegonCasaError("Unexpected Swegon summary response")
        return response

    async def _async_request(
        self, method: str, path: str, payload: dict[str, Any] | None = None
    ) -> Any:
        await self._async_refresh_access_token()
        assert self._access_token is not None
        try:
            async with self._session.request(
                method,
                f"{API_BASE_URL}{path}",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self._access_token}",
                    "User-Agent": APP_USER_AGENT,
                },
                timeout=30,
            ) as response:
                if response.status in {401, 403}:
                    self._access_token = None
                    raise SwegonCasaAuthenticationError(
                        "Swegon CASA access token was rejected"
                    )
                if response.status >= 400:
                    raise SwegonCasaError(
                        f"Swegon CASA returned HTTP {response.status}"
                    )
                if response.content_length == 0:
                    return None
                return await response.json()
        except SwegonCasaError:
            raise
        except (ClientError, TimeoutError, ValueError) as error:
            raise SwegonCasaError("Unable to reach Swegon CASA") from error

    async def _async_refresh_access_token(self, *, force: bool = False) -> None:
        if (
            not force
            and self._access_token is not None
            and datetime.now(UTC) + timedelta(minutes=2)
            < self._access_token_expires_at
        ):
            return

        async with self._refresh_lock:
            if (
                not force
                and self._access_token is not None
                and datetime.now(UTC) + timedelta(minutes=2)
                < self._access_token_expires_at
            ):
                return
            try:
                async with self._session.post(
                    f"{API_BASE_URL}/mobile/user/refresh_access_token",
                    json={"refreshToken": self._refresh_token},
                    headers={
                        "X-API-Key": self._app_api_key,
                        "User-Agent": APP_USER_AGENT,
                    },
                    timeout=30,
                ) as response:
                    if response.status in {401, 403, 404}:
                        raise SwegonCasaAuthenticationError(
                            "Swegon CASA refresh token was rejected"
                        )
                    if response.status >= 400:
                        raise SwegonCasaError(
                            f"Swegon CASA returned HTTP {response.status}"
                        )
                    body = await response.json()
            except SwegonCasaError:
                raise
            except (ClientError, TimeoutError, ValueError) as error:
                raise SwegonCasaError("Unable to refresh Swegon CASA login") from error

            try:
                self._access_token = str(body["accessToken"])
                new_refresh_token = str(body["refreshToken"])
                expires_in = int(body["expiresIn"])
            except (KeyError, TypeError, ValueError) as error:
                raise SwegonCasaError("Invalid Swegon CASA login response") from error

            self._access_token_expires_at = datetime.now(UTC) + timedelta(
                seconds=expires_in
            )
            if new_refresh_token != self._refresh_token:
                self._refresh_token = new_refresh_token
                if self._refresh_token_updated is not None:
                    self._refresh_token_updated(new_refresh_token)
