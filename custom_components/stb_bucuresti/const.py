"""Constants for the STB Bucuresti integration."""

from homeassistant.const import Platform

DOMAIN = "stb_bucuresti"

# Platforms
PLATFORMS: list[Platform] = [Platform.DEVICE_TRACKER, Platform.SENSOR]

# Configuration
CONF_LINES = "lines"  # List of line IDs (internal API IDs)
CONF_LINE_NAMES = "line_names"  # Dict mapping line_id -> line_name (user-facing)
CONF_UPDATE_INTERVAL = "update_interval"

# Defaults
DEFAULT_UPDATE_INTERVAL = 30  # seconds
MIN_UPDATE_INTERVAL = 10
MAX_UPDATE_INTERVAL = 300

# API Configuration
API_BASE_URL = "https://info.stb.ro/api/web/v2-6"
API_TIMEOUT = 15

# App credentials for STB API
API_APP_ID = "6d118493-e28c-4705-ba09-99b926de8c27"
API_APP_KEY = "gcALgRyZHC,qFonZ=Jde"

# Base headers for STB API (User-Info is added dynamically after auth)
API_HEADERS_BASE = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:148.0) Gecko/20100101 Firefox/148.0",
    "Accept": "application/json",
    "OS-Type": "Web",
    "Lang": "ro",
    "App-Version": "0.0.0",
    "Device-Name": "HomeAssistant",
    "OS-Version": "1.0",
    "Source": "ro.radcom.smartcity.web",
    "App-Id": API_APP_ID,
}

# Vehicle types
VEHICLE_TYPE_TRAM = "TRAM"
VEHICLE_TYPE_BUS = "BUS"
VEHICLE_TYPE_TROLLEYBUS = "CABLE_CAR"  # Trolleybus in STB API
VEHICLE_TYPE_SUBWAY = "SUBWAY"

VEHICLE_TYPE_NAMES = {
    VEHICLE_TYPE_TRAM: "Tramvai",
    VEHICLE_TYPE_BUS: "Autobuz",
    VEHICLE_TYPE_TROLLEYBUS: "Troleibuz",
    VEHICLE_TYPE_SUBWAY: "Metrou",
}

VEHICLE_TYPE_ICONS = {
    VEHICLE_TYPE_TRAM: "mdi:tram",
    VEHICLE_TYPE_BUS: "mdi:bus",
    VEHICLE_TYPE_TROLLEYBUS: "mdi:bus-electric",
    VEHICLE_TYPE_SUBWAY: "mdi:subway",
}

# Attribution
ATTRIBUTION = "Date furnizate de STB Bucuresti"
