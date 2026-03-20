"""Data coordinator for STB Bucuresti integration."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import (
    STBApiClient,
    STBApiError,
    STBLine,
    STBVehicle,
)
from .const import CONF_LINE_NAMES, CONF_LINES, CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


class STBDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for STB Bucuresti data updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_client: STBApiClient,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        self.api_client = api_client
        self.config_entry = config_entry
        
        # Get configured lines (list of internal IDs)
        self.monitored_lines: list[int] = config_entry.data.get(CONF_LINES, [])
        
        # Get line name mapping from config (line_id -> {"name": "41", "type": "TRAM"})
        # This allows us to show user-friendly names even before API is loaded
        self._line_names_config: dict[str, dict[str, str]] = config_entry.data.get(
            CONF_LINE_NAMES, {}
        )
        
        # Get update interval
        update_interval = config_entry.data.get(
            CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
        )
        
        super().__init__(
            hass,
            _LOGGER,
            name="STB Bucuresti",
            update_interval=timedelta(seconds=update_interval),
        )
        
        # Cache for line information (from API)
        self._lines_cache: dict[int, STBLine] = {}
        self._lines_loaded = False

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API."""
        try:
            # Load lines info once if not cached
            if not self._lines_loaded:
                await self._load_lines()
            
            # Fetch vehicle positions for all monitored lines
            all_vehicles: list[STBVehicle] = []
            
            for line_id in self.monitored_lines:
                try:
                    vehicles = await self.api_client.async_get_all_vehicles_for_line(
                        line_id
                    )
                    
                    # Enrich with line name
                    line_info = self._lines_cache.get(line_id)
                    for vehicle in vehicles:
                        vehicle.line_id = line_id
                        if line_info:
                            vehicle.line_name = line_info.name
                    
                    all_vehicles.extend(vehicles)
                    
                except STBApiError as err:
                    _LOGGER.warning(
                        "Failed to fetch vehicles for line %s: %s",
                        line_id, err
                    )
            
            return {
                "vehicles": all_vehicles,
                "lines": self._lines_cache,
                "monitored_lines": self.monitored_lines,
            }
        
        except STBApiError as err:
            raise UpdateFailed(f"Error communicating with STB API: {err}") from err
        except Exception as err:
            _LOGGER.exception("Unexpected error updating STB data")
            raise UpdateFailed(f"Unexpected error: {err}") from err

    async def _load_lines(self) -> None:
        """Load all available lines from API."""
        try:
            lines = await self.api_client.async_get_lines()
            self._lines_cache = {line.id: line for line in lines}
            self._lines_loaded = True
            _LOGGER.info("Loaded %d lines from STB API", len(lines))
        except STBApiError as err:
            _LOGGER.error("Failed to load lines: %s", err)
            raise

    async def async_get_all_lines(self) -> list[STBLine]:
        """Get all available lines (for config flow)."""
        if not self._lines_loaded:
            await self._load_lines()
        return list(self._lines_cache.values())

    def get_line_by_id(self, line_id: int | None) -> STBLine | None:
        """Get line info by ID."""
        if line_id is None:
            return None
        return self._lines_cache.get(line_id)

    def get_line_name(self, line_id: int | None) -> str:
        """Get user-friendly line name by ID.
        
        Falls back to config data if API cache isn't loaded yet.
        """
        if line_id is None:
            return "Unknown"
        
        # First try API cache
        line = self._lines_cache.get(line_id)
        if line:
            return line.name
        
        # Fall back to config data
        line_config = self._line_names_config.get(str(line_id))
        if line_config:
            return line_config.get("name", str(line_id))
        
        # Last resort: return the ID as string
        return str(line_id)

    def get_line_type(self, line_id: int | None) -> str:
        """Get line transport type by ID."""
        if line_id is None:
            return "BUS"
        
        # First try API cache
        line = self._lines_cache.get(line_id)
        if line:
            return line.transport_type
        
        # Fall back to config data
        line_config = self._line_names_config.get(str(line_id))
        if line_config:
            return line_config.get("type", "BUS")
        
        return "BUS"

    def get_line_by_name(self, name: str) -> STBLine | None:
        """Get line info by name."""
        for line in self._lines_cache.values():
            if line.name == name:
                return line
        return None

    def get_vehicles_for_line(self, line_id: int) -> list[STBVehicle]:
        """Get vehicles for a specific line from cached data."""
        if not self.data:
            return []
        
        vehicles = self.data.get("vehicles", [])
        return [v for v in vehicles if v.line_id == line_id]

    def get_all_vehicles(self) -> list[STBVehicle]:
        """Get all vehicles from cached data."""
        if not self.data:
            return []
        return self.data.get("vehicles", [])
