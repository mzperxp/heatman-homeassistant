"""Sensor platform for Heatman locations (temperature and setpoint) and system metrics."""

from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.helpers.entity import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HeatmanBatteryCoordinator, HeatmanDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


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


class HeatmanBatterySensor(CoordinatorEntity[HeatmanBatteryCoordinator], SensorEntity):
    """Battery level sensor for a Heatman BLE sensor. Attached to the location device so it appears in the same area."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: HeatmanBatteryCoordinator,
        entry: ConfigEntry,
        sensor_id: str,
        sensor_name: str,
        location_id: str,
        location_name: str,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._sensor_id = sensor_id
        display = sensor_name or sensor_id
        self._attr_name = f"{display} battery"
        self._attr_unique_id = f"{entry.entry_id}_{sensor_id}_battery"
        # Use location device so this entity appears on the same device (and area) as the climate/temp/setpoint
        self._attr_device_info = _device_info(
            entry.entry_id,
            location_id,
            location_name,
        )
        self._update_from_data()

    def _update_from_data(self) -> None:
        battery = None
        for s in self.coordinator.data or []:
            if s.get("id") == self._sensor_id:
                val = s.get("batteryLevel")
                if val is not None:
                    try:
                        battery = int(float(val))
                    except (TypeError, ValueError):
                        pass
                break
        self._attr_native_value = battery

    @callback
    def _handle_coordinator_update(self) -> None:
        self._update_from_data()
        super()._handle_coordinator_update()


class HeatmanCpuTemperatureSensor(SensorEntity):
    """CPU temperature sensor for the Heatman backend host."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: HeatmanDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        self._coordinator = coordinator
        self._entry = entry
        self._attr_name = "Heatman CPU temperature"
        self._attr_unique_id = f"{entry.entry_id}_cpu_temperature"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{entry.entry_id}_system")},
            "name": "Heatman system",
            "manufacturer": "Heatman",
            "model": "Controller",
        }

    async def async_update(self) -> None:
        """Fetch latest CPU temperature from backend."""
        try:
            temp = await self._coordinator.async_get_cpu_temperature()
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Failed to fetch Heatman CPU temperature: %s", err)
            temp = None

        self._attr_native_value = float(temp) if temp is not None else None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Heatman sensors from a config entry."""
    coordinator: HeatmanDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    battery_coordinator: HeatmanBatteryCoordinator = hass.data[DOMAIN][entry.entry_id]["battery_coordinator"]
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

    # Single system-wide CPU temperature sensor
    entities.append(HeatmanCpuTemperatureSensor(coordinator, entry))

    # Battery sensors: one per sensor with battery, on the location device so they show in that area
    await battery_coordinator.async_config_entry_first_refresh()
    for s in battery_coordinator.data or []:
        if s.get("batteryLevel") is None:
            continue
        sensor_id = s.get("id")
        loc = s.get("location") or {}
        location_id = loc.get("id")
        if not sensor_id or not location_id:
            continue
        location_name = loc.get("name") or "Unknown"
        name = s.get("name") or sensor_id
        entities.append(
            HeatmanBatterySensor(
                battery_coordinator,
                entry,
                sensor_id,
                name,
                location_id,
                location_name,
            )
        )

    async_add_entities(entities)
