"""Config flow for STB Bucuresti integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .api import STBApiClient, STBApiError, STBLine
from .const import (
    CONF_LINE_NAMES,
    CONF_LINES,
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    MAX_UPDATE_INTERVAL,
    MIN_UPDATE_INTERVAL,
    VEHICLE_TYPE_NAMES,
)

_LOGGER = logging.getLogger(__name__)


class STBConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for STB Bucuresti."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._lines: list[STBLine] = []
        self._api_client: STBApiClient | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate connection to API
            session = async_get_clientsession(self.hass)
            self._api_client = STBApiClient(session)

            try:
                # Test connection and fetch lines
                self._lines = await self._api_client.async_get_lines()

                if not self._lines:
                    errors["base"] = "no_lines"
                else:
                    # Move to line selection
                    return await self.async_step_select_lines()

            except STBApiError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during setup")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({}),
            errors=errors,
            description_placeholders={
                "info": "This integration connects to STB Bucuresti to track public transport vehicles in real-time."
            },
        )

    async def async_step_select_lines(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle line selection step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            selected_lines = user_input.get(CONF_LINES, [])
            update_interval = user_input.get(
                CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
            )

            if not selected_lines:
                errors["base"] = "no_lines_selected"
            else:
                # Convert line display names to IDs and build name mapping
                line_ids = []
                line_names: dict[int, dict[str, str]] = {}
                
                for line_display in selected_lines:
                    for line in self._lines:
                        display = f"{line.name} ({VEHICLE_TYPE_NAMES.get(line.transport_type, line.transport_type)})"
                        if display == line_display:
                            line_ids.append(line.id)
                            # Store both name and type for each line ID
                            line_names[line.id] = {
                                "name": line.name,
                                "type": line.transport_type,
                            }
                            break

                if not line_ids:
                    errors["base"] = "no_lines_selected"
                else:
                    # Create unique ID based on selected line names (user-friendly)
                    selected_names = [line_names[lid]["name"] for lid in line_ids[:5]]
                    unique_id = f"stb_{'-'.join(sorted(selected_names))}"
                    await self.async_set_unique_id(unique_id)
                    self._abort_if_unique_id_configured()

                    return self.async_create_entry(
                        title="STB Bucuresti",
                        data={
                            CONF_LINES: line_ids,
                            CONF_LINE_NAMES: line_names,
                            CONF_UPDATE_INTERVAL: update_interval,
                        },
                    )

        # Build line options grouped by type
        line_options = []
        
        # Sort lines by type and name
        sorted_lines = sorted(
            self._lines,
            key=lambda x: (x.transport_type, x.name.zfill(10)),
        )

        for line in sorted_lines:
            type_name = VEHICLE_TYPE_NAMES.get(line.transport_type, line.transport_type)
            label = f"{line.name} ({type_name})"
            line_options.append({"value": label, "label": label})

        schema = vol.Schema(
            {
                vol.Required(CONF_LINES): SelectSelector(
                    SelectSelectorConfig(
                        options=line_options,
                        multiple=True,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(
                    CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_INTERVAL
                ): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_UPDATE_INTERVAL, max=MAX_UPDATE_INTERVAL),
                ),
            }
        )

        return self.async_show_form(
            step_id="select_lines",
            data_schema=schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> STBOptionsFlow:
        """Get the options flow for this handler."""
        return STBOptionsFlow(config_entry)


class STBOptionsFlow(config_entries.OptionsFlow):
    """Handle options for STB Bucuresti."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry
        self._lines: list[STBLine] = []
        self._api_client: STBApiClient | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}

        # Get current values
        current_lines = self._config_entry.data.get(CONF_LINES, [])
        current_interval = self._config_entry.data.get(
            CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
        )

        if user_input is not None:
            new_interval = user_input.get(CONF_UPDATE_INTERVAL, current_interval)

            # Update the config entry
            self.hass.config_entries.async_update_entry(
                self._config_entry,
                data={
                    **self._config_entry.data,
                    CONF_UPDATE_INTERVAL: new_interval,
                },
            )

            return self.async_create_entry(data={})

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_UPDATE_INTERVAL, default=current_interval
                ): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_UPDATE_INTERVAL, max=MAX_UPDATE_INTERVAL),
                ),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "lines_count": str(len(current_lines)),
            },
        )
