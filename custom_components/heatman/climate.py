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

    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
    )
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
        scenes: list[dict[str, Any]],
    ) -> None:
        """Initialize the climate entity."""
        super().__init__(coordinator)
        self._entry = entry
        self._location_id = location_id
        self._attr_name = f"{location_name} heating"
        self._attr_unique_id = f"{entry.entry_id}_{location_id}_climate"
        self._attr_device_info = _device_info(entry.entry_id, location_id, location_name)
        self._attr_hvac_mode = HVACMode.HEAT
        # Map scene name -> scene id for preset_mode (only existing Heatman scenes)
        self._scene_name_to_id: dict[str, str] = {}
        for s in scenes:
            sid = s.get("id")
            sname = s.get("name") or sid
            if sid and sname:
                self._scene_name_to_id[sname] = sid
        self._attr_preset_modes = list(self._scene_name_to_id.keys())
        self._attr_preset_mode = None
        self._scene_rules_fetched = False
        self._update_from_data()

    def _update_from_data(self) -> None:
        """Set state from coordinator data."""
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

    async def _update_preset_from_scene_rules(self) -> None:
        """Set preset_mode from active scene rule for this location (once per entity)."""
        if self._scene_rules_fetched:
            return
        self._scene_rules_fetched = True
        try:
            rules = await self.coordinator.async_get_scene_rules_for_location(
                self._location_id
            )
            for r in rules:
                if r.get("isActive"):
                    name = r.get("sceneName")
                    if name and name in self._scene_name_to_id:
                        self._attr_preset_mode = name
                        self.async_write_ha_state()
                        break
        except Exception:
            pass

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_from_data()
        # Once per entity: fetch scene rules to show current active scene
        if not self._scene_rules_fetched and self._attr_preset_modes:
            self.coordinator.hass.async_create_task(self._update_preset_from_scene_rules())
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
        await self.coordinator.async_request_refresh()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Enable the selected scene (static scene rule) for this location."""
        scene_id = self._scene_name_to_id.get(preset_mode)
        if not scene_id:
            return
        await self.coordinator.async_enable_scene_rule(
            self._location_id,
            scene_id,
        )
        self._attr_preset_mode = preset_mode
        self.async_write_ha_state()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Heatman climate entities from a config entry."""
    coordinator: HeatmanDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[ClimateEntity] = []

    try:
        scenes = await coordinator.async_fetch_scenes()
    except Exception:
        scenes = []

    for loc in coordinator.data or []:
        loc_id = loc.get("id")
        name = loc.get("name") or loc_id or "Unknown"
        if not loc_id:
            continue
        entities.append(
            HeatmanClimate(coordinator, entry, loc_id, name, scenes=scenes)
        )

    async_add_entities(entities)

