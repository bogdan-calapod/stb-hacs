"""Device tracker platform for STB Bucuresti vehicles."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import STBVehicle
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
    """Set up STB Bucuresti device trackers."""
    coordinator: STBDataUpdateCoordinator = entry.runtime_data.coordinator

    # Create a tracker for each vehicle we see
    entities: list[STBVehicleTracker] = []
    tracked_vehicles: set[str] = set()

    @callback
    def _async_add_new_vehicles() -> None:
        """Add device trackers for new vehicles."""
        if not coordinator.data:
            return

        vehicles = coordinator.data.get("vehicles", [])
        new_entities = []

        for vehicle in vehicles:
            vehicle_key = f"{vehicle.line_id}_{vehicle.vehicle_number}"
            
            if vehicle_key not in tracked_vehicles:
                tracked_vehicles.add(vehicle_key)
                entity = STBVehicleTracker(coordinator, vehicle)
                new_entities.append(entity)
                _LOGGER.debug(
                    "Adding vehicle tracker: %s (%s)",
                    vehicle.vehicle_number,
                    vehicle.vehicle_type,
                )

        if new_entities:
            async_add_entities(new_entities)

    # Add current vehicles
    _async_add_new_vehicles()

    # Listen for new vehicles in future updates
    entry.async_on_unload(
        coordinator.async_add_listener(_async_add_new_vehicles)
    )


class STBVehicleTracker(CoordinatorEntity[STBDataUpdateCoordinator], TrackerEntity):
    """Tracker for an STB vehicle."""

    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION

    def __init__(
        self,
        coordinator: STBDataUpdateCoordinator,
        vehicle: STBVehicle,
    ) -> None:
        """Initialize the vehicle tracker."""
        super().__init__(coordinator)
        
        self._vehicle_number = vehicle.vehicle_number
        self._vehicle_type = vehicle.vehicle_type
        self._line_id = vehicle.line_id
        
        # Get user-friendly line name (e.g., "41" instead of internal ID "57")
        self._line_name = coordinator.get_line_name(vehicle.line_id)
        
        # Set unique ID using line name for readability
        self._attr_unique_id = f"stb_line{self._line_name}_{self._vehicle_number}"
        
        # Set entity name - user sees "Tramvai 3804 - Linia 41"
        type_name = VEHICLE_TYPE_NAMES.get(self._vehicle_type, self._vehicle_type)
        self._attr_name = f"{type_name} {self._vehicle_number} - Linia {self._line_name}"
        
        # Set icon based on vehicle type
        self._attr_icon = VEHICLE_TYPE_ICONS.get(self._vehicle_type, "mdi:bus")
        
        # Store initial position
        self._latitude = vehicle.latitude
        self._longitude = vehicle.longitude
        self._direction = vehicle.direction

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        # Use user-friendly line name
        line_name = self.coordinator.get_line_name(self._line_id)
        line_type = self.coordinator.get_line_type(self._line_id)
        
        return DeviceInfo(
            identifiers={(DOMAIN, f"line_{self._line_name}")},
            name=f"STB Linia {line_name}",
            manufacturer="STB Bucuresti",
            model=VEHICLE_TYPE_NAMES.get(line_type, line_type),
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def source_type(self) -> SourceType:
        """Return the source type."""
        return SourceType.GPS

    @property
    def latitude(self) -> float | None:
        """Return latitude."""
        vehicle = self._get_vehicle()
        if vehicle:
            return vehicle.latitude
        return self._latitude

    @property
    def longitude(self) -> float | None:
        """Return longitude."""
        vehicle = self._get_vehicle()
        if vehicle:
            return vehicle.longitude
        return self._longitude

    @property
    def location_name(self) -> str | None:
        """Return a location name for the current location."""
        return f"Linia {self._line_name}"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        vehicle = self._get_vehicle()
        line_info = self.coordinator.get_line_by_id(self._line_id)
        
        attrs = {
            "vehicle_number": self._vehicle_number,
            "vehicle_type": VEHICLE_TYPE_NAMES.get(self._vehicle_type, self._vehicle_type),
            "line": self._line_name,  # User-friendly line name (e.g., "41")
            "direction": self._direction,
        }
        
        if vehicle:
            attrs["direction"] = vehicle.direction
            self._direction = vehicle.direction
        
        if line_info:
            attrs["line_color"] = line_info.color
        
        return attrs

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # Check if we still have this vehicle in the data
        return self._get_vehicle() is not None

    def _get_vehicle(self) -> STBVehicle | None:
        """Get current vehicle data from coordinator."""
        if not self.coordinator.data:
            return None
        
        vehicles = self.coordinator.data.get("vehicles", [])
        for vehicle in vehicles:
            if (
                vehicle.line_id == self._line_id
                and vehicle.vehicle_number == self._vehicle_number
            ):
                return vehicle
        
        return None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        vehicle = self._get_vehicle()
        if vehicle:
            self._latitude = vehicle.latitude
            self._longitude = vehicle.longitude
            self._direction = vehicle.direction
        
        super()._handle_coordinator_update()
