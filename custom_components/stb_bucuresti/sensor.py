"""Sensor platform for STB Bucuresti integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTRIBUTION,
    DOMAIN,
    VEHICLE_TYPE_ICONS,
    VEHICLE_TYPE_NAMES,
)
from .coordinator import STBDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up STB Bucuresti sensors."""
    coordinator: STBDataUpdateCoordinator = entry.runtime_data.coordinator

    entities: list[SensorEntity] = []

    # Create a sensor for each monitored line showing vehicle count
    for line_id in coordinator.monitored_lines:
        # Use get_line_name which falls back to config data if API not loaded
        line_name = coordinator.get_line_name(line_id)
        entities.append(
            STBLineVehicleCountSensor(coordinator, line_id, line_name)
        )

    # Create a total vehicles sensor
    entities.append(STBTotalVehiclesSensor(coordinator))

    async_add_entities(entities)


class STBLineVehicleCountSensor(
    CoordinatorEntity[STBDataUpdateCoordinator], SensorEntity
):
    """Sensor showing the number of active vehicles on a line."""

    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION

    def __init__(
        self,
        coordinator: STBDataUpdateCoordinator,
        line_id: int,
        line_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        
        self._line_id = line_id
        self._line_name = line_name  # User-friendly name like "41"
        
        # Get line type (TRAM, BUS, etc.)
        self._vehicle_type = coordinator.get_line_type(line_id)
        
        # Set unique ID using line name for readability
        self._attr_unique_id = f"stb_line_{line_name}_count"
        self._attr_name = f"Linia {line_name} - Vehicule active"
        
        # Set icon
        self._attr_icon = VEHICLE_TYPE_ICONS.get(self._vehicle_type, "mdi:bus")
        
        # Set unit
        self._attr_native_unit_of_measurement = "vehicule"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"line_{self._line_name}")},
            name=f"STB Linia {self._line_name}",
            manufacturer="STB Bucuresti",
            model=VEHICLE_TYPE_NAMES.get(self._vehicle_type, self._vehicle_type),
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> int:
        """Return the number of vehicles."""
        vehicles = self.coordinator.get_vehicles_for_line(self._line_id)
        return len(vehicles)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        vehicles = self.coordinator.get_vehicles_for_line(self._line_id)
        line_info = self.coordinator.get_line_by_id(self._line_id)
        
        attrs = {
            "line": self._line_name,  # User-friendly name like "41"
            "vehicle_type": VEHICLE_TYPE_NAMES.get(self._vehicle_type, self._vehicle_type),
            "vehicle_numbers": [v.vehicle_number for v in vehicles],
        }
        
        # Count by direction
        dir_0 = len([v for v in vehicles if v.direction == 0])
        dir_1 = len([v for v in vehicles if v.direction == 1])
        attrs["direction_0_count"] = dir_0
        attrs["direction_1_count"] = dir_1
        
        if line_info:
            attrs["line_color"] = line_info.color
            attrs["has_disabled_access"] = line_info.has_disabled_access
        
        return attrs


class STBTotalVehiclesSensor(CoordinatorEntity[STBDataUpdateCoordinator], SensorEntity):
    """Sensor showing total number of tracked vehicles."""

    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION
    _attr_icon = "mdi:bus-multiple"
    _attr_native_unit_of_measurement = "vehicule"

    def __init__(self, coordinator: STBDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        
        self._attr_unique_id = "stb_total_vehicles"
        self._attr_name = "STB Total Vehicule Active"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, "stb_bucuresti")},
            name="STB Bucuresti",
            manufacturer="STB Bucuresti",
            model="Transport Public",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> int:
        """Return total number of vehicles."""
        return len(self.coordinator.get_all_vehicles())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        vehicles = self.coordinator.get_all_vehicles()
        
        # Count by type
        by_type: dict[str, int] = {}
        for vehicle in vehicles:
            type_name = VEHICLE_TYPE_NAMES.get(
                vehicle.vehicle_type, vehicle.vehicle_type
            ) or "Unknown"
            by_type[type_name] = by_type.get(type_name, 0) + 1
        
        # Count by line
        by_line: dict[str, int] = {}
        for vehicle in vehicles:
            if vehicle.line_id is not None:
                line_info = self.coordinator.get_line_by_id(vehicle.line_id)
                line_name = line_info.name if line_info else str(vehicle.line_id)
            else:
                line_name = "Unknown"
            by_line[line_name] = by_line.get(line_name, 0) + 1
        
        return {
            "monitored_lines_count": len(self.coordinator.monitored_lines),
            "vehicles_by_type": by_type,
            "vehicles_by_line": by_line,
        }
