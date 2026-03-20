"""STB Bucuresti integration for Home Assistant.

This integration provides real-time tracking of public transport vehicles
(trams, buses, trolleybuses) in Bucharest, Romania.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import STBApiClient
from .const import DOMAIN, PLATFORMS
from .coordinator import STBDataUpdateCoordinator

if TYPE_CHECKING:
    pass

_LOGGER = logging.getLogger(__name__)


@dataclass
class STBRuntimeData:
    """Runtime data for STB Bucuresti integration."""

    coordinator: STBDataUpdateCoordinator
    api_client: STBApiClient


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up STB Bucuresti from a config entry."""
    _LOGGER.info("Setting up STB Bucuresti integration")

    # Create API client
    session = async_get_clientsession(hass)
    api_client = STBApiClient(session)

    # Create coordinator
    coordinator = STBDataUpdateCoordinator(
        hass,
        api_client=api_client,
        config_entry=entry,
    )

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    # Store runtime data
    entry.runtime_data = STBRuntimeData(
        coordinator=coordinator,
        api_client=api_client,
    )

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register update listener
    entry.async_on_unload(entry.add_update_listener(_async_update_options))

    _LOGGER.info(
        "STB Bucuresti integration set up successfully with %d lines",
        len(coordinator.monitored_lines),
    )

    return True


async def _async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    _LOGGER.info("STB Bucuresti options updated, reloading")
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading STB Bucuresti integration")

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.debug("Migrating STB Bucuresti from version %s", config_entry.version)

    if config_entry.version == 1:
        # No migration needed for version 1
        pass

    _LOGGER.info("Migration to version %s successful", config_entry.version)
    return True
