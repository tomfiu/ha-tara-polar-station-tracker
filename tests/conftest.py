"""Shared test fixtures for Tara Polar Station Tracker tests."""
from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Minimal homeassistant stubs so tests run without installing the full HA
# package. These must be registered in sys.modules BEFORE any integration
# code is imported.
# ---------------------------------------------------------------------------

def _stub(name: str) -> ModuleType:
    mod = ModuleType(name)
    sys.modules[name] = mod
    return mod


if "homeassistant" not in sys.modules:
    for _n in [
        "homeassistant",
        "homeassistant.core",
        "homeassistant.config_entries",
        "homeassistant.const",
        "homeassistant.helpers",
        "homeassistant.helpers.storage",
        "homeassistant.helpers.update_coordinator",
        "homeassistant.helpers.device_registry",
        "homeassistant.helpers.entity_platform",
        "homeassistant.helpers.aiohttp_client",
        "homeassistant.components",
        "homeassistant.components.sensor",
        "homeassistant.components.binary_sensor",
        "homeassistant.components.camera",
        "homeassistant.data_entry_flow",
    ]:
        _stub(_n)

    # DataUpdateCoordinator needs to be a real class: TaraPolarStationCoordinator
    # inherits from it and relies on update_interval, hass, and data attributes.
    class _DataUpdateCoordinator:
        def __class_getitem__(cls, item):  # support DataUpdateCoordinator[T]
            return cls

        def __init__(self, hass, logger, *, name, update_interval, **kwargs):
            self.hass = hass
            self.name = name
            self.update_interval = update_interval
            self.data = None

        async def async_refresh(self):
            pass

    class _CoordinatorEntity:
        def __class_getitem__(cls, item):
            return cls

        def __init__(self, coordinator, **kwargs):
            self.coordinator = coordinator

    _upc = sys.modules["homeassistant.helpers.update_coordinator"]
    _upc.DataUpdateCoordinator = _DataUpdateCoordinator
    _upc.CoordinatorEntity = _CoordinatorEntity

    class _DeviceInfo(dict):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)

    class _DeviceEntryType:
        SERVICE = "service"

    _dr = sys.modules["homeassistant.helpers.device_registry"]
    _dr.DeviceInfo = _DeviceInfo
    _dr.DeviceEntryType = _DeviceEntryType

    class _Platform:
        SENSOR = "sensor"
        BINARY_SENSOR = "binary_sensor"
        CAMERA = "camera"

    sys.modules["homeassistant.core"].HomeAssistant = MagicMock
    sys.modules["homeassistant.core"].callback = lambda f: f
    sys.modules["homeassistant.config_entries"].ConfigEntry = MagicMock
    sys.modules["homeassistant.config_entries"].ConfigFlow = MagicMock
    sys.modules["homeassistant.config_entries"].OptionsFlow = MagicMock
    sys.modules["homeassistant.const"].Platform = _Platform
    sys.modules["homeassistant.helpers.storage"].Store = MagicMock
    sys.modules["homeassistant.helpers.entity_platform"].AddEntitiesCallback = MagicMock
    sys.modules["homeassistant.helpers.aiohttp_client"].async_get_clientsession = MagicMock
    sys.modules["homeassistant.components.sensor"].SensorEntity = MagicMock
    sys.modules["homeassistant.components.sensor"].SensorEntityDescription = MagicMock
    sys.modules["homeassistant.components.sensor"].SensorStateClass = MagicMock
    sys.modules["homeassistant.components.sensor"].SensorDeviceClass = MagicMock
    sys.modules["homeassistant.components.binary_sensor"].BinarySensorEntity = MagicMock
    sys.modules["homeassistant.components.binary_sensor"].BinarySensorEntityDescription = MagicMock
    sys.modules["homeassistant.components.camera"].Camera = MagicMock
    sys.modules["homeassistant.data_entry_flow"].FlowResult = dict


@pytest.fixture
def sample_ais_message() -> dict:
    """Return a sample AISStream PositionReport message."""
    return {
        "MessageType": "PositionReport",
        "MetaData": {
            "MMSI": 228471700,
            "ShipName": "TARA POLAR STATION",
            "latitude": 79.332,
            "longitude": -23.992,
            "time_utc": "2026-08-15 12:30:00.000000 +0000 UTC",
        },
        "Message": {
            "PositionReport": {
                "MessageID": 1,
                "UserID": 228471700,
                "NavigationalStatus": 0,
                "Sog": 0.3,
                "Cog": 45.0,
                "Longitude": -23.992,
                "Latitude": 79.332,
                "TrueHeading": 511,
                "Timestamp": 30,
                "Valid": True,
            }
        },
    }


@pytest.fixture
def sample_raw_telemetry() -> dict:
    """Return parsed raw telemetry dict (as produced by coordinator._parse_position)."""
    return {
        "latitude": 79.332,
        "longitude": -23.992,
        "speed": 0.3,
        "course": 45.0,
        "heading": 511,
        "nav_status": 0,
        "timestamp": "2026-08-15 12:30:00.000000 +0000 UTC",
    }
