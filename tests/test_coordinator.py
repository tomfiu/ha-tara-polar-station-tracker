"""Tests for the Tara Polar Station coordinator."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from custom_components.tara_polar_station.coordinator import (
    TaraPolarStationCoordinator,
)


class TestParsePosition:
    """Test the _parse_position static method."""

    def test_parse_valid_message(self, sample_ais_message):
        """Parse a valid AISStream PositionReport."""
        result = TaraPolarStationCoordinator._parse_position(
            sample_ais_message
        )
        assert result["latitude"] == pytest.approx(79.332)
        assert result["longitude"] == pytest.approx(-23.992)
        assert result["speed"] == pytest.approx(0.3)
        assert result["course"] == pytest.approx(45.0)
        assert result["timestamp"] is not None

    def test_parse_missing_metadata_falls_back(self):
        """When MetaData has no lat/lon, use PositionReport fields."""
        msg = {
            "MessageType": "PositionReport",
            "MetaData": {"time_utc": "2026-01-01 00:00:00.000000 +0000 UTC"},
            "Message": {
                "PositionReport": {
                    "Latitude": 70.5,
                    "Longitude": 10.2,
                    "Sog": 5.0,
                    "Cog": 180.0,
                    "TrueHeading": 180,
                    "NavigationalStatus": 0,
                }
            },
        }
        result = TaraPolarStationCoordinator._parse_position(msg)
        assert result["latitude"] == pytest.approx(70.5)
        assert result["longitude"] == pytest.approx(10.2)
        assert result["speed"] == pytest.approx(5.0)


class TestComputeDerived:
    """Test the _compute_derived method."""

    def _make_coordinator(
        self,
        home_lat: float = 50.0,
        home_lon: float = 14.0,
        departure_date: str = "2026-07-01",
    ) -> TaraPolarStationCoordinator:
        """Create a coordinator instance with a mock hass."""
        hass = MagicMock()
        hass.bus = MagicMock()
        coord = TaraPolarStationCoordinator(
            hass=hass,
            api_key="test",
            poll_interval=15,
            home_lat=home_lat,
            home_lon=home_lon,
            departure_date=departure_date,
        )
        return coord

    def test_derived_values_present(self, sample_raw_telemetry):
        """All derived keys should be present in output."""
        coord = self._make_coordinator()
        result = coord._compute_derived(sample_raw_telemetry)

        expected_keys = [
            "distance_from_home",
            "distance_to_north_pole",
            "bearing_from_home",
            "bearing_compass",
            "in_arctic_circle",
            "in_polar_day",
            "in_polar_night",
            "solar_elevation",
            "local_sunrise",
            "local_sunset",
            "stationary",
            "days_since_departure",
            "mission_phase",
        ]
        for key in expected_keys:
            assert key in result, f"Missing key: {key}"

    def test_arctic_circle_detection(self, sample_raw_telemetry):
        """79.332°N should be inside the Arctic Circle."""
        coord = self._make_coordinator()
        result = coord._compute_derived(sample_raw_telemetry)
        assert result["in_arctic_circle"] is True

    def test_below_arctic_circle(self):
        """50°N should be outside the Arctic Circle."""
        coord = self._make_coordinator()
        raw = {
            "latitude": 50.0,
            "longitude": 14.0,
            "speed": 5.0,
            "course": 0.0,
            "heading": 0,
            "nav_status": 0,
            "timestamp": "2026-08-15 12:00:00.000000 +0000 UTC",
        }
        result = coord._compute_derived(raw)
        assert result["in_arctic_circle"] is False

    def test_stationary_detection(self, sample_raw_telemetry):
        """Speed 0.3 kn (below 0.5 threshold) should be stationary."""
        coord = self._make_coordinator()
        result = coord._compute_derived(sample_raw_telemetry)
        assert result["stationary"] is True

    def test_moving_detection(self):
        """Speed 5.0 kn should not be stationary."""
        coord = self._make_coordinator()
        raw = {
            "latitude": 70.0,
            "longitude": 0.0,
            "speed": 5.0,
            "course": 90.0,
            "heading": 90,
            "nav_status": 0,
            "timestamp": "2026-08-15 12:00:00.000000 +0000 UTC",
        }
        result = coord._compute_derived(raw)
        assert result["stationary"] is False

    def test_distance_to_north_pole(self, sample_raw_telemetry):
        """Distance from 79.332°N to North Pole should be ~1180 km."""
        coord = self._make_coordinator()
        result = coord._compute_derived(sample_raw_telemetry)
        assert 1100 < result["distance_to_north_pole"] < 1250

    def test_pre_departure_phase(self):
        """Before departure date, phase should be Pre-departure."""
        coord = self._make_coordinator(departure_date="2099-01-01")
        raw = {
            "latitude": 50.0,
            "longitude": 14.0,
            "speed": 0.0,
            "course": 0.0,
            "heading": 0,
            "nav_status": 0,
            "timestamp": "2026-08-15 12:00:00.000000 +0000 UTC",
        }
        result = coord._compute_derived(raw)
        assert result["mission_phase"] == "Pre-departure"

    def test_drifting_phase(self, sample_raw_telemetry):
        """After departure, low speed → Drifting."""
        coord = self._make_coordinator(departure_date="2026-01-01")
        result = coord._compute_derived(sample_raw_telemetry)
        assert result["mission_phase"] == "Drifting"

    def test_transit_phase(self):
        """After departure, high speed → Transit."""
        coord = self._make_coordinator(departure_date="2026-01-01")
        raw = {
            "latitude": 70.0,
            "longitude": 0.0,
            "speed": 5.0,
            "course": 90.0,
            "heading": 90,
            "nav_status": 0,
            "timestamp": "2026-08-15 12:00:00.000000 +0000 UTC",
        }
        result = coord._compute_derived(raw)
        assert result["mission_phase"] == "Transit"

    def test_none_coordinates(self):
        """Missing coordinates should produce None derived values."""
        coord = self._make_coordinator()
        raw = {
            "latitude": None,
            "longitude": None,
            "speed": 0.0,
            "course": 0.0,
            "heading": None,
            "nav_status": None,
            "timestamp": None,
        }
        result = coord._compute_derived(raw)
        assert result["distance_from_home"] is None
        assert result["distance_to_north_pole"] is None
        assert result["in_arctic_circle"] is False
