"""API client for STB Bucuresti.

This module handles communication with the info.stb.ro API,
which returns data in protobuf format.
"""

from __future__ import annotations

import asyncio
import logging
import ssl
import struct
from dataclasses import dataclass
from typing import Any

from aiohttp import ClientSession, ClientTimeout

from .const import (
    API_APP_ID,
    API_APP_KEY,
    API_BASE_URL,
    API_HEADERS_BASE,
    API_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)

# SSL context to bypass certificate verification (STB's cert may cause issues)
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE


class STBApiError(Exception):
    """General STB API error."""


class STBApiConnectionError(STBApiError):
    """Connection error."""


class STBApiTimeoutError(STBApiError):
    """Timeout error."""


@dataclass
class STBLine:
    """Represents a public transport line."""

    id: int
    name: str
    transport_type: str
    color: str
    organization_id: int
    has_disabled_access: bool


@dataclass
class STBStation:
    """Represents a station/stop."""

    id: int
    name: str
    address: str
    latitude: float
    longitude: float


@dataclass
class STBVehicle:
    """Represents a vehicle with real-time position."""

    id: int
    vehicle_number: str
    vehicle_type: str
    latitude: float
    longitude: float
    direction: int
    line_id: int | None = None
    line_name: str | None = None


class STBApiClient:
    """Client for the STB Bucuresti API."""

    def __init__(self, session: ClientSession) -> None:
        """Initialize the API client."""
        self._session = session
        self._timeout = ClientTimeout(total=API_TIMEOUT)
        self._user_info: str | None = None

    async def _ensure_authenticated(self) -> None:
        """Ensure we have a valid auth token."""
        if self._user_info is not None:
            return
        
        await self._authenticate()

    async def _authenticate(self) -> None:
        """Fetch a fresh auth token from the API."""
        url = f"{API_BASE_URL}/proxy/user/auth"
        headers = {
            "App-key": API_APP_KEY,
            "App-Id": API_APP_ID,
            "User-Agent": API_HEADERS_BASE["User-Agent"],
        }
        
        _LOGGER.debug("Authenticating with STB API")
        
        try:
            async with self._session.get(
                url,
                headers=headers,
                timeout=self._timeout,
                ssl=_SSL_CTX,
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    self._user_info = data.get("data", {}).get("userInfo")
                    if self._user_info:
                        _LOGGER.debug("Successfully authenticated with STB API")
                        return
                
                _LOGGER.error("Auth failed with status %s", response.status)
                raise STBApiError(f"Authentication failed: HTTP {response.status}")
        except STBApiError:
            raise
        except Exception as err:
            _LOGGER.error("Auth error: %s", err)
            raise STBApiConnectionError(f"Authentication error: {err}") from err

    def _get_headers(self) -> dict[str, str]:
        """Get headers with current auth token."""
        headers = dict(API_HEADERS_BASE)
        if self._user_info:
            headers["User-Info"] = self._user_info
        return headers

    async def _get(self, endpoint: str, retry_auth: bool = True) -> bytes:
        """Make a GET request and return raw bytes."""
        await self._ensure_authenticated()
        
        url = f"{API_BASE_URL}{endpoint}"
        _LOGGER.debug("GET %s", url)

        try:
            async with self._session.get(
                url,
                headers=self._get_headers(),
                timeout=self._timeout,
                ssl=_SSL_CTX,
            ) as response:
                if response.status == 200:
                    return await response.read()
                
                # Handle 412 Precondition Failed - token expired
                if response.status == 412 and retry_auth:
                    _LOGGER.info("Got 412, refreshing auth token")
                    self._user_info = None
                    await self._authenticate()
                    return await self._get(endpoint, retry_auth=False)
                
                text = await response.text()
                _LOGGER.error("HTTP %s: %s", response.status, text[:500])
                raise STBApiError(f"HTTP {response.status}")

        except asyncio.TimeoutError as err:
            _LOGGER.error("Timeout for %s", endpoint)
            raise STBApiTimeoutError("Request timeout") from err
        except STBApiError:
            raise
        except Exception as err:
            _LOGGER.error("Error for %s: %s", endpoint, err)
            raise STBApiConnectionError(str(err)) from err

    async def async_get_agency_info(self) -> dict[str, Any]:
        """Get agency information (returns JSON)."""
        await self._ensure_authenticated()
        
        url = f"{API_BASE_URL}/agency?lang=ro"
        
        try:
            async with self._session.get(
                url,
                headers=self._get_headers(),
                timeout=self._timeout,
                ssl=_SSL_CTX,
            ) as response:
                if response.status == 200:
                    return await response.json()
                raise STBApiError(f"HTTP {response.status}")
        except Exception as err:
            _LOGGER.error("Error getting agency info: %s", err)
            raise STBApiConnectionError(str(err)) from err

    async def async_get_lines(self) -> list[STBLine]:
        """Get all available lines."""
        data = await self._get("/lines?lang=ro")
        return self._parse_lines(data)

    async def async_get_line_details(self, line_id: int) -> dict[str, Any]:
        """Get detailed information about a specific line."""
        data = await self._get(f"/lines/{line_id}?lang=ro")
        return self._parse_line_details(data)

    async def async_get_line_direction(
        self, line_id: int, direction: int
    ) -> dict[str, Any]:
        """Get line direction details including stations."""
        data = await self._get(f"/lines/{line_id}/direction/{direction}?lang=ro")
        return self._parse_line_direction(data)

    async def async_get_vehicles(
        self, line_id: int, direction: int
    ) -> list[STBVehicle]:
        """Get real-time vehicle positions for a line and direction."""
        data = await self._get(f"/lines/v2/{line_id}/vehicles/{direction}?lang=ro")
        return self._parse_vehicles(data, line_id)

    async def async_get_all_vehicles_for_line(
        self, line_id: int
    ) -> list[STBVehicle]:
        """Get all vehicles for a line (both directions)."""
        vehicles = []
        
        for direction in (0, 1):
            try:
                direction_vehicles = await self.async_get_vehicles(line_id, direction)
                for v in direction_vehicles:
                    v.direction = direction
                vehicles.extend(direction_vehicles)
            except STBApiError as err:
                _LOGGER.warning(
                    "Failed to get vehicles for line %s direction %s: %s",
                    line_id, direction, err
                )
        
        return vehicles

    def _parse_lines(self, data: bytes) -> list[STBLine]:
        """Parse lines from protobuf data."""
        lines = []
        pos = 0
        
        while pos < len(data):
            # Look for message start (0x0a = field 1, length-delimited)
            if data[pos] != 0x0a:
                pos += 1
                continue
            
            pos += 1
            if pos >= len(data):
                break
                
            # Read message length (varint)
            msg_len, varint_len = self._read_varint(data, pos)
            pos += varint_len
            
            if pos + msg_len > len(data):
                break
            
            msg = data[pos:pos + msg_len]
            pos += msg_len
            
            try:
                line = self._parse_line_message(msg)
                if line:
                    lines.append(line)
            except Exception as err:
                _LOGGER.debug("Failed to parse line: %s", err)
        
        return lines

    def _parse_line_message(self, msg: bytes) -> STBLine | None:
        """Parse a single line message."""
        fields: dict[int, Any] = {}
        i = 0
        
        while i < len(msg):
            if i >= len(msg):
                break
                
            tag = msg[i]
            field_num = tag >> 3
            wire_type = tag & 0x07
            i += 1
            
            if wire_type == 0:  # Varint
                val, vlen = self._read_varint(msg, i)
                fields[field_num] = val
                i += vlen
            elif wire_type == 1:  # Fixed64
                if i + 8 <= len(msg):
                    fields[field_num] = struct.unpack('<d', msg[i:i+8])[0]
                    i += 8
            elif wire_type == 2:  # Length-delimited
                if i < len(msg):
                    str_len, vlen = self._read_varint(msg, i)
                    i += vlen
                    if i + str_len <= len(msg):
                        try:
                            fields[field_num] = msg[i:i+str_len].decode('utf-8')
                        except UnicodeDecodeError:
                            fields[field_num] = msg[i:i+str_len]
                        i += str_len
            elif wire_type == 5:  # Fixed32
                if i + 4 <= len(msg):
                    fields[field_num] = struct.unpack('<I', msg[i:i+4])[0]
                    i += 4
            else:
                # Unknown wire type, skip
                break
        
        # Fields mapping based on analysis:
        # 1: id
        # 2: name
        # 3: transport_type
        # 4: (unknown)
        # 5: color (hex string)
        # ...
        
        if 1 not in fields or 2 not in fields:
            return None
        
        return STBLine(
            id=fields.get(1, 0),
            name=str(fields.get(2, "")),
            transport_type=str(fields.get(3, "BUS")),
            color=str(fields.get(5, "#1D71B8")),
            organization_id=fields.get(8, 1),
            has_disabled_access="BU" in str(fields.get(4, "")),
        )

    def _parse_vehicles(self, data: bytes, line_id: int) -> list[STBVehicle]:
        """Parse vehicles from protobuf data."""
        vehicles = []
        pos = 0
        
        while pos < len(data):
            # Look for message start
            if data[pos] != 0x0a:
                pos += 1
                continue
            
            pos += 1
            if pos >= len(data):
                break
            
            # Read message length
            msg_len, varint_len = self._read_varint(data, pos)
            pos += varint_len
            
            if pos + msg_len > len(data):
                break
            
            msg = data[pos:pos + msg_len]
            pos += msg_len
            
            try:
                vehicle = self._parse_vehicle_message(msg, line_id)
                if vehicle:
                    vehicles.append(vehicle)
            except Exception as err:
                _LOGGER.debug("Failed to parse vehicle: %s", err)
        
        return vehicles

    def _parse_vehicle_message(self, msg: bytes, line_id: int) -> STBVehicle | None:
        """Parse a single vehicle message."""
        fields: dict[int, Any] = {}
        i = 0
        
        while i < len(msg):
            if i >= len(msg):
                break
                
            tag = msg[i]
            field_num = tag >> 3
            wire_type = tag & 0x07
            i += 1
            
            if wire_type == 0:  # Varint
                val, vlen = self._read_varint(msg, i)
                fields[field_num] = val
                i += vlen
            elif wire_type == 1:  # Fixed64 (double)
                if i + 8 <= len(msg):
                    fields[field_num] = struct.unpack('<d', msg[i:i+8])[0]
                    i += 8
            elif wire_type == 2:  # Length-delimited (string)
                if i < len(msg):
                    str_len, vlen = self._read_varint(msg, i)
                    i += vlen
                    if i + str_len <= len(msg):
                        try:
                            fields[field_num] = msg[i:i+str_len].decode('utf-8')
                        except UnicodeDecodeError:
                            fields[field_num] = msg[i:i+str_len]
                        i += str_len
            else:
                break
        
        # Fields based on analysis:
        # 1: internal_id
        # 2: latitude
        # 3: longitude
        # 4: vehicle_number (string)
        # 5: vehicle_type (TRAM, BUS, etc.)
        # 6: direction (1 or 0)
        
        if 2 not in fields or 3 not in fields:
            return None
        
        return STBVehicle(
            id=fields.get(1, 0),
            vehicle_number=str(fields.get(4, "")),
            vehicle_type=str(fields.get(5, "BUS")),
            latitude=float(fields.get(2, 0)),
            longitude=float(fields.get(3, 0)),
            direction=int(fields.get(6, 0)),
            line_id=line_id,
        )

    def _parse_line_details(self, data: bytes) -> dict[str, Any]:
        """Parse line details from protobuf data."""
        # For now, return basic info extracted from the binary
        result = {
            "stations": [],
            "raw_data": data,
        }
        
        # Extract station names from strings
        strings = self._extract_strings(data)
        result["station_names"] = strings
        
        return result

    def _parse_line_direction(self, data: bytes) -> dict[str, Any]:
        """Parse line direction details from protobuf data."""
        result = {
            "stations": [],
            "raw_data": data,
        }
        
        strings = self._extract_strings(data)
        result["station_names"] = strings
        
        return result

    def _extract_strings(self, data: bytes) -> list[str]:
        """Extract readable strings from binary data."""
        strings = []
        try:
            # Simple string extraction
            decoded = data.decode('utf-8', errors='ignore')
            # Filter for location names (typically capitalized words)
            import re
            matches = re.findall(r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*', decoded)
            strings = [m for m in matches if len(m) > 3]
        except Exception:
            pass
        return strings

    @staticmethod
    def _read_varint(data: bytes, pos: int) -> tuple[int, int]:
        """Read a varint from data at position. Returns (value, bytes_read)."""
        result = 0
        shift = 0
        bytes_read = 0
        
        while pos + bytes_read < len(data):
            b = data[pos + bytes_read]
            result |= (b & 0x7F) << shift
            bytes_read += 1
            if b < 0x80:
                break
            shift += 7
        
        return result, bytes_read
