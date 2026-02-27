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
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = 5.0
    _attr_max_temp = 30.0

    PRESET_NONE = "None"

    def __init__(
        self,
        coordinator: HeatmanDataUpdateCoordinator,
        entry: ConfigEntry,
        location_id: str,
        location_name: str,
        scenes: list[dict[str, Any]],
        is_root: bool,
    ) -> None:
        """Initialize the climate entity."""
        super().__init__(coordinator)
        self._entry = entry
        self._location_id = location_id
        self._attr_name = f"{location_name} heating"
        self._attr_unique_id = f"{entry.entry_id}_{location_id}_climate"
        self._attr_device_info = _device_info(entry.entry_id, location_id, location_name)

        # Root location exposes system operating mode as HEAT/COOL and allows changing it.
        # Other locations are read-only for mode and just show current system mode.
        self._is_root = is_root
        if self._is_root:
            self._attr_hvac_modes = [HVACMode.HEAT, HVACMode.COOL]
        else:
            self._attr_hvac_modes = [HVACMode.HEAT]
        self._attr_hvac_mode = HVACMode.HEAT
        # Map scene name -> scene id for preset_mode (only existing Heatman scenes)
        self._scene_name_to_id: dict[str, str] = {}
        for s in scenes:
            sid = s.get("id")
            sname = s.get("name") or sid
            if sid and sname:
                self._scene_name_to_id[sname] = sid
        # Add a special "no preset" option in addition to real scenes
        self._attr_preset_modes = list(self._scene_name_to_id.keys()) + [self.PRESET_NONE]
        self._attr_preset_mode = self.PRESET_NONE
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
                # For non-root entities, keep hvac_mode in sync with system mode (coordinator attribute).
                # Root entity will be updated explicitly when mode changes.
                return

    async def _update_preset_from_backend(self) -> None:
        """Set preset_mode from backend active scene preset for this location (once per entity)."""
        if self._scene_rules_fetched:
            return
        self._scene_rules_fetched = True
        try:
            preset = await self.coordinator.async_get_active_scene_preset(
                self._location_id
            )
            if not preset:
                # No active preset from backend; keep or reset to None
                self._attr_preset_mode = self.PRESET_NONE
                self.async_write_ha_state()
                return
            name = preset.get("sceneName")
            if name and name in self._scene_name_to_id:
                self._attr_preset_mode = name
            else:
                self._attr_preset_mode = self.PRESET_NONE
            self.async_write_ha_state()
        except Exception:
            pass

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_from_data()
        # Once per entity: fetch active preset from backend to show current scene
        if not self._scene_rules_fetched and self._attr_preset_modes:
            self.coordinator.hass.async_create_task(self._update_preset_from_backend())
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
        """Set or clear the active scene preset for this location."""
        if preset_mode == self.PRESET_NONE:
            await self.coordinator.async_clear_active_scene_preset(self._location_id)
            self._attr_preset_mode = self.PRESET_NONE
            self.async_write_ha_state()
            return

        scene_id = self._scene_name_to_id.get(preset_mode)
        if not scene_id:
            return

        await self.coordinator.async_set_active_scene_preset(
            self._location_id,
            scene_id,
        )
        self._attr_preset_mode = preset_mode
        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Only root location can change system operating mode."""
        if not self._is_root:
            # Ignore mode changes for non-root locations
            return

        if hvac_mode == HVACMode.HEAT:
            await self.coordinator.async_set_operating_mode("HEATING")
        elif hvac_mode == HVACMode.COOL:
            await self.coordinator.async_set_operating_mode("COOLING")
        else:
            return

        self._attr_hvac_mode = hvac_mode
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

    # Fetch current operating mode once, so all entities start with correct hvac_mode
    try:
        operating_mode = await coordinator.async_get_operating_mode()
    except Exception:
        operating_mode = "HEATING"

    initial_hvac = HVACMode.HEAT if operating_mode == "HEATING" else HVACMode.COOL

    for loc in coordinator.data or []:
        loc_id = loc.get("id")
        name = loc.get("name") or loc_id or "Unknown"
        is_root = bool(loc.get("is_root"))
        if not loc_id:
            continue
        climate = HeatmanClimate(
            coordinator,
            entry,
            loc_id,
            name,
            scenes=scenes,
            is_root=is_root,
        )
        climate._attr_hvac_mode = initial_hvac
        entities.append(climate)

    async_add_entities(entities)

