"""Config flow for the Heatman integration."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_BASE_URL, DOMAIN, API_PATH_LOGIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_BASE_URL): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


def _normalize_base_url(url: str) -> str:
    """Normalize base URL (strip trailing slash, default scheme)."""
    url = url.strip().rstrip("/")
    if url and not url.startswith(("http://", "https://")):
        url = f"http://{url}"
    return url


async def _validate_credentials(
    base_url: str, username: str, password: str, session
) -> None:
    """Validate credentials by calling the Heatman login API."""
    login_url = f"{base_url}{API_PATH_LOGIN}"
    payload = {"username": username, "password": password}

    async with session.post(login_url, json=payload, timeout=10) as resp:
        if resp.status != 200:
            text = await resp.text()
            _LOGGER.warning("Login failed: status=%s body=%s", resp.status, text[:200])
            raise ConnectionError(f"Login failed: HTTP {resp.status}")
        data = await resp.json()
        if not data.get("accessToken"):
            raise ConnectionError("Invalid response: no access token")


class HeatmanConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Heatman."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            base_url = _normalize_base_url(user_input[CONF_BASE_URL])
            username = user_input[CONF_USERNAME].strip()
            password = user_input[CONF_PASSWORD]

            try:
                session = async_get_clientsession(self.hass)
                await _validate_credentials(base_url, username, password, session)
            except ConnectionError as e:
                errors["base"] = str(e)
            except TimeoutError:
                errors["base"] = "Connection timed out"
            except Exception as e:
                _LOGGER.exception("Unexpected error validating Heatman connection")
                errors["base"] = f"Unexpected error: {e!s}"

            if not errors:
                await self.async_set_unique_id(base_url)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=base_url,
                    data={
                        CONF_BASE_URL: base_url,
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
