"""Data update coordinator for Heatman."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    API_PATH_LOGIN,
    API_PATH_TREE_WITH_STATE,
    CONF_BASE_URL,
    CONF_PASSWORD,
    CONF_USERNAME,
    DEFAULT_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


def _flatten_locations_with_state(node: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten tree of locations with state into a list."""
    out: list[dict[str, Any]] = []
    loc_id = node.get("id")
    name = node.get("name") or loc_id or "Unknown"
    out.append(
        {
            "id": loc_id,
            "name": name,
            "current_temp": node.get("currentTemp"),
            "current_setpoint": node.get("currentSetpoint"),
            "actuator_setpoint": node.get("actuatorSetpoint"),
        }
    )
    for child in node.get("childrenWithState") or []:
        out.extend(_flatten_locations_with_state(child))
    return out


class HeatmanDataUpdateCoordinator(DataUpdateCoordinator[list[dict[str, Any]]]):
    """Coordinator that fetches location state from Heatman API."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="heatman",
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self._entry = entry
        self._session = async_get_clientsession(hass)
        self._access_token: str | None = None

    def _base_url(self) -> str:
        return self._entry.data[CONF_BASE_URL]

    async def _ensure_token(self) -> str:
        """Login and return access token."""
        url = f"{self._base_url()}{API_PATH_LOGIN}"
        payload = {
            "username": self._entry.data[CONF_USERNAME],
            "password": self._entry.data[CONF_PASSWORD],
        }
        async with self._session.post(url, json=payload, timeout=10) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise UpdateFailed(f"Login failed: HTTP {resp.status} - {text[:100]}")
            data = await resp.json()
            token = data.get("accessToken")
            if not token:
                raise UpdateFailed("Login response missing accessToken")
            self._access_token = token
            return token

    async def _async_update_data(self) -> list[dict[str, Any]]:
        """Fetch tree-with-state and return flattened location list."""
        token = await self._ensure_token()
        url = f"{self._base_url()}{API_PATH_TREE_WITH_STATE}"
        params = {"mode": "HEATING"}

        async with self._session.get(
            url,
            params=params,
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        ) as resp:
            if resp.status == 401:
                self._access_token = None
                raise UpdateFailed("Unauthorized; credentials may have changed")
            if resp.status != 200:
                text = await resp.text()
                raise UpdateFailed(f"API error: HTTP {resp.status} - {text[:100]}")
            root = await resp.json()

        locations = _flatten_locations_with_state(root)
        _LOGGER.debug("Fetched %d locations with state", len(locations))
        return locations
