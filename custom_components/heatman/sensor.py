"""Sensor platform for Heatman locations (temperature and setpoint)."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HeatmanDataUpdateCoordinator


def _device_info(entry_id: str, location_id: str, location_name: str) -> dict:
    """Build device info for a location."""
    return {
        "identifiers": {(DOMAIN, f"{entry_id}_{location_id}")},
        "name": location_name,
        "manufacturer": "Heatman",
        "model": "Location",
    }


class HeatmanTemperatureSensor(CoordinatorEntity[HeatmanDataUpdateCoordinator], SensorEntity):
    """Current temperature sensor for a Heatman location."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: HeatmanDataUpdateCoordinator,
        entry: ConfigEntry,
        location_id: str,
        location_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._location_id = location_id
        self._attr_name = f"{location_name} temperature"
        self._attr_unique_id = f"{entry.entry_id}_{location_id}_temperature"
        self._attr_device_info = _device_info(
            entry.entry_id, location_id, location_name
        )
        self._update_from_data()

    def _update_from_data(self) -> None:
        """Set state from coordinator data."""
        for loc in self.coordinator.data or []:
            if loc.get("id") == self._location_id:
                temp = loc.get("current_temp")
                self._attr_native_value = float(temp) if temp is not None else None
                return

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_from_data()
        super()._handle_coordinator_update()


class HeatmanSetpointSensor(CoordinatorEntity[HeatmanDataUpdateCoordinator], SensorEntity):
    """Current setpoint sensor for a Heatman location."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: HeatmanDataUpdateCoordinator,
        entry: ConfigEntry,
        location_id: str,
        location_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._location_id = location_id
        self._attr_name = f"{location_name} setpoint"
        self._attr_unique_id = f"{entry.entry_id}_{location_id}_setpoint"
        self._attr_device_info = _device_info(
            entry.entry_id, location_id, location_name
        )
        self._update_from_data()

    def _update_from_data(self) -> None:
        """Set state from coordinator data."""
        for loc in self.coordinator.data or []:
            if loc.get("id") == self._location_id:
                setpoint = loc.get("current_setpoint")
                self._attr_native_value = float(setpoint) if setpoint is not None else None
                return

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_from_data()
        super()._handle_coordinator_update()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Heatman sensors from a config entry."""
    coordinator: HeatmanDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = []

    for loc in coordinator.data or []:
        loc_id = loc.get("id")
        name = loc.get("name") or loc_id or "Unknown"
        if not loc_id:
            continue
        entities.append(
            HeatmanTemperatureSensor(coordinator, entry, loc_id, name)
        )
        entities.append(
            HeatmanSetpointSensor(coordinator, entry, loc_id, name)
        )

    async_add_entities(entities)
