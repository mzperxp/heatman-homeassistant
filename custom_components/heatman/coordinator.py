"""Data update coordinator for Heatman."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.exceptions import HomeAssistantError

from .const import (
    API_PATH_LOGIN,
    API_PATH_TREE_WITH_STATE,
    API_PATH_MANUAL_OVERRIDES,
    API_PATH_SCENES,
    API_PATH_SCENE_RULES,
    CONF_BASE_URL,
    CONF_PASSWORD,
    CONF_USERNAME,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_OVERRIDE_DURATION_MINUTES,
    DEFAULT_SCENE_RULE_HEATING_TEMP,
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
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self._entry = entry
        self._session = async_get_clientsession(hass)
        self._access_token: str | None = None

    def _base_url(self) -> str:
        return self._entry.data[CONF_BASE_URL]

    async def _ensure_token(self) -> str:
        """Login and return access token."""
        url = f"{self._base_url()}{API_PATH_LOGIN}"
        _LOGGER.debug("Heatman login: %s", url)
        payload = {
            "username": self._entry.data[CONF_USERNAME],
            "password": self._entry.data[CONF_PASSWORD],
        }
        try:
            async with self._session.post(url, json=payload, timeout=10) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    _LOGGER.error("Heatman login failed: %s -> HTTP %s %s", url, resp.status, text[:200])
                    raise UpdateFailed(f"Login failed: HTTP {resp.status} - {text[:100]}")
                try:
                    data = await resp.json()
                except (aiohttp.ContentTypeError, ValueError) as e:
                    _LOGGER.error("Heatman login: invalid JSON from %s: %s", url, e)
                    raise UpdateFailed("Login response was not valid JSON") from e
            token = data.get("accessToken")
            if not token:
                raise UpdateFailed("Login response missing accessToken")
            self._access_token = token
            return token
        except aiohttp.ClientError as e:
            _LOGGER.error("Heatman connection error to %s: %s", url, e)
            raise UpdateFailed(f"Cannot connect to Heatman at {self._base_url()}: {e!s}") from e

    async def async_create_manual_override(
        self,
        location_id: str,
        temperature: float,
        duration_minutes: int | None = DEFAULT_OVERRIDE_DURATION_MINUTES,
    ) -> None:
        """Create a manual override for a location via the Heatman API."""
        token = await self._ensure_token()
        url = f"{self._base_url()}{API_PATH_MANUAL_OVERRIDES}"
        payload: dict[str, Any] = {
            "locationId": location_id,
            "temperature": float(temperature),
            "durationMinutes": duration_minutes,
        }
        _LOGGER.debug(
            "Creating Heatman manual override: url=%s, payload=%s",
            url,
            payload,
        )

        try:
            async with self._session.post(
                url,
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
                timeout=15,
            ) as resp:
                if resp.status not in (200, 201):
                    text = await resp.text()
                    _LOGGER.error(
                        "Heatman manual override failed: %s -> HTTP %s %s",
                        url,
                        resp.status,
                        text[:200],
                    )
                    raise HomeAssistantError(
                        f"Failed to create manual override: HTTP {resp.status}"
                    )
                # We don't need the response body for now; just ensure it's valid JSON if present
                try:
                    if resp.content_type == "application/json":
                        await resp.json()
                except (aiohttp.ContentTypeError, ValueError):
                    # Non-JSON or empty body is acceptable; just log at debug level
                    _LOGGER.debug("Heatman manual override response was not JSON")
        except aiohttp.ClientError as e:
            _LOGGER.error("Heatman connection error to %s: %s", url, e)
            raise HomeAssistantError(f"Cannot connect to Heatman at {self._base_url()}: {e!s}") from e

    async def async_fetch_scenes(self) -> list[dict[str, Any]]:
        """Fetch all scenes (for validation; only existing Heatman scenes may be used)."""
        token = await self._ensure_token()
        url = f"{self._base_url()}{API_PATH_SCENES}"
        try:
            async with self._session.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
                timeout=15,
            ) as resp:
                if resp.status == 401:
                    self._access_token = None
                    raise HomeAssistantError("Unauthorized")
                if resp.status != 200:
                    text = await resp.text()
                    _LOGGER.error("Heatman scenes API error: %s -> HTTP %s %s", url, resp.status, text[:200])
                    raise HomeAssistantError(f"Failed to fetch scenes: HTTP {resp.status}")
                data = await resp.json()
                return data if isinstance(data, list) else []
        except aiohttp.ClientError as e:
            _LOGGER.error("Heatman connection error to %s: %s", url, e)
            raise HomeAssistantError(f"Cannot connect to Heatman: {e!s}") from e

    async def async_get_scene_rules_for_location(self, location_id: str) -> list[dict[str, Any]]:
        """Get all scene rules for a location."""
        token = await self._ensure_token()
        url = f"{self._base_url()}{API_PATH_SCENE_RULES}/location/{location_id}"
        try:
            async with self._session.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
                timeout=15,
            ) as resp:
                if resp.status == 401:
                    self._access_token = None
                    raise HomeAssistantError("Unauthorized")
                if resp.status != 200:
                    text = await resp.text()
                    _LOGGER.error("Heatman scene rules API error: %s -> HTTP %s %s", url, resp.status, text[:200])
                    raise HomeAssistantError(f"Failed to fetch scene rules: HTTP {resp.status}")
                data = await resp.json()
                return data if isinstance(data, list) else []
        except aiohttp.ClientError as e:
            _LOGGER.error("Heatman connection error to %s: %s", url, e)
            raise HomeAssistantError(f"Cannot connect to Heatman: {e!s}") from e

    async def async_enable_scene_rule(
        self,
        location_id: str,
        scene_id: str,
        heating_temperature: float | None = None,
        cooling_temperature: float | None = None,
    ) -> None:
        """Enable a scene rule for a location: create if missing (with default temps), else set active."""
        token = await self._ensure_token()
        rules = await self.async_get_scene_rules_for_location(location_id)
        existing = next((r for r in rules if r.get("sceneId") == scene_id), None)

        if existing:
            rule_id = existing.get("id")
            url = f"{self._base_url()}{API_PATH_SCENE_RULES}/{rule_id}"
            payload: dict[str, Any] = {"isActive": True}
            _LOGGER.debug("Enabling existing scene rule: %s", rule_id)
            try:
                async with self._session.put(
                    url,
                    json=payload,
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=15,
                ) as resp:
                    if resp.status not in (200, 204):
                        text = await resp.text()
                        _LOGGER.error("Heatman enable scene rule failed: %s -> HTTP %s %s", url, resp.status, text[:200])
                        raise HomeAssistantError(f"Failed to enable scene rule: HTTP {resp.status}")
            except aiohttp.ClientError as e:
                _LOGGER.error("Heatman connection error to %s: %s", url, e)
                raise HomeAssistantError(f"Cannot connect to Heatman: {e!s}") from e
        else:
            # Create new scene rule; backend requires at least one temperature
            heating = heating_temperature if heating_temperature is not None else DEFAULT_SCENE_RULE_HEATING_TEMP
            cooling = cooling_temperature
            payload = {
                "locationId": location_id,
                "sceneId": scene_id,
                "heatingTemperature": heating,
                "coolingTemperature": cooling,
            }
            url = f"{self._base_url()}{API_PATH_SCENE_RULES}"
            _LOGGER.debug("Creating scene rule: location=%s scene=%s heating=%s", location_id, scene_id, heating)
            try:
                async with self._session.post(
                    url,
                    json=payload,
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=15,
                ) as resp:
                    if resp.status not in (200, 201):
                        text = await resp.text()
                        _LOGGER.error("Heatman create scene rule failed: %s -> HTTP %s %s", url, resp.status, text[:200])
                        raise HomeAssistantError(f"Failed to create scene rule: HTTP {resp.status}")
            except aiohttp.ClientError as e:
                _LOGGER.error("Heatman connection error to %s: %s", url, e)
                raise HomeAssistantError(f"Cannot connect to Heatman: {e!s}") from e

        await self.async_request_refresh()

    async def async_disable_scene_rule(self, location_id: str, scene_id: str) -> None:
        """Disable the scene rule for this location and scene (set isActive false)."""
        token = await self._ensure_token()
        rules = await self.async_get_scene_rules_for_location(location_id)
        existing = next((r for r in rules if r.get("sceneId") == scene_id), None)
        if not existing:
            _LOGGER.warning("No scene rule found for location=%s scene=%s", location_id, scene_id)
            return
        rule_id = existing.get("id")
        url = f"{self._base_url()}{API_PATH_SCENE_RULES}/{rule_id}"
        payload: dict[str, Any] = {"isActive": False}
        try:
            async with self._session.put(
                url,
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
                timeout=15,
            ) as resp:
                if resp.status not in (200, 204):
                    text = await resp.text()
                    _LOGGER.error("Heatman disable scene rule failed: %s -> HTTP %s %s", url, resp.status, text[:200])
                    raise HomeAssistantError(f"Failed to disable scene rule: HTTP {resp.status}")
        except aiohttp.ClientError as e:
            _LOGGER.error("Heatman connection error to %s: %s", url, e)
            raise HomeAssistantError(f"Cannot connect to Heatman: {e!s}") from e
        await self.async_request_refresh()

    async def _async_update_data(self) -> list[dict[str, Any]]:
        """Fetch tree-with-state and return flattened location list."""
        try:
            token = await self._ensure_token()
        except UpdateFailed:
            raise

        url = f"{self._base_url()}{API_PATH_TREE_WITH_STATE}"
        params = {"mode": "HEATING"}
        _LOGGER.debug("Heatman fetch: %s", url)

        try:
            async with self._session.get(
                url,
                params=params,
                headers={"Authorization": f"Bearer {token}"},
                timeout=15,
            ) as resp:
                if resp.status == 401:
                    self._access_token = None
                    _LOGGER.error("Heatman API unauthorized at %s", url)
                    raise UpdateFailed("Unauthorized; credentials may have changed")
                if resp.status != 200:
                    text = await resp.text()
                    _LOGGER.error("Heatman API error: %s -> HTTP %s %s", url, resp.status, text[:200])
                    raise UpdateFailed(f"API error: HTTP {resp.status} - {text[:100]}")
                try:
                    root = await resp.json()
                except (aiohttp.ContentTypeError, ValueError) as e:
                    _LOGGER.error("Heatman API: invalid JSON from %s: %s", url, e)
                    raise UpdateFailed("API response was not valid JSON") from e
        except aiohttp.ClientError as e:
            _LOGGER.error("Heatman connection error to %s: %s", url, e)
            raise UpdateFailed(f"Cannot connect to Heatman at {self._base_url()}: {e!s}") from e

        if not isinstance(root, dict):
            _LOGGER.error("Heatman API: expected JSON object, got %s", type(root).__name__)
            raise UpdateFailed("API returned unexpected data")

        locations = _flatten_locations_with_state(root)
        _LOGGER.debug("Fetched %d locations with state", len(locations))
        return locations
