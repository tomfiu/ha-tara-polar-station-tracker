"""Shared test fixtures for Tara Polar Station Tracker tests."""
from __future__ import annotations

import pytest


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
