"""Heatman integration for Home Assistant."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
import voluptuous as vol

from .const import DOMAIN
from .coordinator import HeatmanDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.CLIMATE]

SERVICE_ENABLE_SCENE_RULE = "enable_scene_rule"
SERVICE_DISABLE_SCENE_RULE = "disable_scene_rule"

SCENE_RULE_SCHEMA = vol.Schema(
    {
        vol.Required("location_id"): cv.string,
        vol.Required("scene_id"): cv.string,
        vol.Optional("heating_temperature"): vol.Coerce(float),
        vol.Optional("cooling_temperature"): vol.Coerce(float),
    }
)
SCENE_RULE_DISABLE_SCHEMA = vol.Schema(
    {
        vol.Required("location_id"): cv.string,
        vol.Required("scene_id"): cv.string,
    }
)


def _get_coordinator(hass: HomeAssistant):
    """Return the first Heatman coordinator (single-server setup)."""
    data = hass.data.get(DOMAIN)
    if not data:
        return None
    return next(iter(data.values()), None)


async def _handle_enable_scene_rule(call):
    """Service handler to enable a scene rule on a location."""
    hass = call.context.hass
    coordinator = _get_coordinator(hass)
    if not coordinator:
        raise ValueError("Heatman integration not configured")
    await coordinator.async_enable_scene_rule(
        location_id=call.data["location_id"],
        scene_id=call.data["scene_id"],
        heating_temperature=call.data.get("heating_temperature"),
        cooling_temperature=call.data.get("cooling_temperature"),
    )


async def _handle_disable_scene_rule(call):
    """Service handler to disable a scene rule on a location."""
    hass = call.context.hass
    coordinator = _get_coordinator(hass)
    if not coordinator:
        raise ValueError("Heatman integration not configured")
    await coordinator.async_disable_scene_rule(
        location_id=call.data["location_id"],
        scene_id=call.data["scene_id"],
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Heatman from a config entry."""
    coordinator = HeatmanDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    if len(hass.data[DOMAIN]) == 1:
        hass.services.async_register(
            DOMAIN,
            SERVICE_ENABLE_SCENE_RULE,
            _handle_enable_scene_rule,
            schema=SCENE_RULE_SCHEMA,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_DISABLE_SCENE_RULE,
            _handle_disable_scene_rule,
            schema=SCENE_RULE_DISABLE_SCHEMA,
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id, None)
        if not hass.data.get(DOMAIN):
            hass.services.async_remove(DOMAIN, SERVICE_ENABLE_SCENE_RULE)
            hass.services.async_remove(DOMAIN, SERVICE_DISABLE_SCENE_RULE)
    return unload_ok
