"""Climate platform for Heatman locations (thermostat-style control)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HeatmanDataUpdateCoordinator
from .sensor import _device_info


class HeatmanClimate(CoordinatorEntity[HeatmanDataUpdateCoordinator], ClimateEntity):
    """Climate entity representing a Heatman location."""

    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_hvac_modes = [HVACMode.HEAT]
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = 5.0
    _attr_max_temp = 30.0

    def __init__(
        self,
        coordinator: HeatmanDataUpdateCoordinator,
        entry: ConfigEntry,
        location_id: str,
        location_name: str,
    ) -> None:
        """Initialize the climate entity."""
        super().__init__(coordinator)
        self._entry = entry
        self._location_id = location_id
        self._attr_name = f"{location_name} heating"
        self._attr_unique_id = f"{entry.entry_id}_{location_id}_climate"
        self._attr_device_info = _device_info(entry.entry_id, location_id, location_name)
        self._attr_hvac_mode = HVACMode.HEAT
        self._update_from_data()

    def _update_from_data(self) -> None:
        """Update state from coordinator data."""
        for loc in self.coordinator.data or []:
            if loc.get("id") == self._location_id:
                current_temp = loc.get("current_temp")
                current_setpoint = loc.get("current_setpoint")
                self._attr_current_temperature = (
                    float(current_temp) if current_temp is not None else None
                )
                self._attr_target_temperature = (
                    float(current_setpoint) if current_setpoint is not None else None
                )
                return

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_from_data()
        super()._handle_coordinator_update()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature by creating a manual override."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        await self.coordinator.async_create_manual_override(
            self._location_id,
            float(temperature),
        )

        # Request a refresh so sensors and this entity reflect the new setpoint
        await self.coordinator.async_request_refresh()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Heatman climate entities from a config entry."""
    coordinator: HeatmanDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[ClimateEntity] = []

    for loc in coordinator.data or []:
        loc_id = loc.get("id")
        name = loc.get("name") or loc_id or "Unknown"
        if not loc_id:
            continue
        entities.append(HeatmanClimate(coordinator, entry, loc_id, name))

    async_add_entities(entities)

