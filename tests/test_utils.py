"""Tests for utility functions."""
from __future__ import annotations

import math
from datetime import datetime, timezone

import pytest

from custom_components.tara_polar_station.utils import (
    calculate_bearing,
    compass_direction,
    haversine_distance,
    is_polar_day,
    is_polar_night,
    parse_ais_timestamp,
)


class TestHaversineDistance:
    """Test haversine distance calculation."""

    def test_same_point(self):
        """Distance between the same point should be zero."""
        assert haversine_distance(50.0, 14.0, 50.0, 14.0) == pytest.approx(
            0.0, abs=0.01
        )

    def test_known_distance(self):
        """Test a known distance: Prague to London ~1035 km."""
        dist = haversine_distance(50.0755, 14.4378, 51.5074, -0.1278)
        assert dist == pytest.approx(1035, rel=0.05)

    def test_north_pole_distance(self):
        """Distance from equator to North Pole should be ~10008 km."""
        dist = haversine_distance(0.0, 0.0, 90.0, 0.0)
        assert dist == pytest.approx(10008, rel=0.01)

    def test_antipodal_points(self):
        """Distance between antipodal points ~20015 km (half circumference)."""
        dist = haversine_distance(0.0, 0.0, 0.0, 180.0)
        assert dist == pytest.approx(20015, rel=0.01)

    def test_arctic_distance(self):
        """Test distance in Arctic region."""
        # Svalbard to North Pole
        dist = haversine_distance(78.22, 15.64, 90.0, 0.0)
        assert 1200 < dist < 1400


class TestCalculateBearing:
    """Test bearing calculation."""

    def test_due_north(self):
        """Bearing due north should be ~0 degrees."""
        bearing = calculate_bearing(50.0, 0.0, 60.0, 0.0)
        assert bearing == pytest.approx(0.0, abs=0.5)

    def test_due_east(self):
        """Bearing due east should be ~90 degrees."""
        bearing = calculate_bearing(0.0, 0.0, 0.0, 10.0)
        assert bearing == pytest.approx(90.0, abs=0.5)

    def test_due_south(self):
        """Bearing due south should be ~180 degrees."""
        bearing = calculate_bearing(60.0, 0.0, 50.0, 0.0)
        assert bearing == pytest.approx(180.0, abs=0.5)

    def test_due_west(self):
        """Bearing due west should be ~270 degrees."""
        bearing = calculate_bearing(0.0, 10.0, 0.0, 0.0)
        assert bearing == pytest.approx(270.0, abs=0.5)

    def test_bearing_range(self):
        """Bearing should always be 0-360."""
        for lat in range(-80, 80, 20):
            for lon in range(-180, 180, 30):
                b = calculate_bearing(0.0, 0.0, float(lat), float(lon))
                assert 0.0 <= b < 360.0


class TestCompassDirection:
    """Test compass direction conversion."""

    def test_north(self):
        assert compass_direction(0.0) == "N"
        assert compass_direction(360.0) == "N"

    def test_east(self):
        assert compass_direction(90.0) == "E"

    def test_south(self):
        assert compass_direction(180.0) == "S"

    def test_west(self):
        assert compass_direction(270.0) == "W"

    def test_northeast(self):
        assert compass_direction(45.0) == "NE"

    def test_all_directions(self):
        """All 16 compass points should be reachable."""
        directions = set()
        for deg in range(0, 360, 1):
            directions.add(compass_direction(float(deg)))
        assert len(directions) == 16


class TestPolarDayNight:
    """Test polar day/night detection."""

    def test_polar_day_summer_arctic(self):
        """High-latitude summer should have polar day."""
        # June 21 at 80°N — expect polar day
        dt = datetime(2026, 6, 21, 12, 0, tzinfo=timezone.utc)
        assert is_polar_day(80.0, 0.0, dt) is True
        assert is_polar_night(80.0, 0.0, dt) is False

    def test_polar_night_winter_arctic(self):
        """High-latitude winter should have polar night."""
        # December 21 at 80°N — expect polar night
        dt = datetime(2026, 12, 21, 12, 0, tzinfo=timezone.utc)
        assert is_polar_night(80.0, 0.0, dt) is True
        assert is_polar_day(80.0, 0.0, dt) is False

    def test_no_polar_day_at_equator(self):
        """Equatorial locations should never have polar day or night."""
        dt = datetime(2026, 6, 21, 12, 0, tzinfo=timezone.utc)
        assert is_polar_day(0.0, 0.0, dt) is False
        assert is_polar_night(0.0, 0.0, dt) is False


class TestParseAisTimestamp:
    """Test AIS timestamp parsing."""

    def test_aisstream_format(self):
        """Parse AISStream's timestamp format."""
        ts = "2026-08-15 12:30:00.000000 +0000 UTC"
        result = parse_ais_timestamp(ts)
        assert result is not None
        assert result.year == 2026
        assert result.month == 8
        assert result.day == 15
        assert result.hour == 12
        assert result.minute == 30
        assert result.tzinfo is not None

    def test_iso_format(self):
        """Parse ISO 8601 format."""
        ts = "2026-08-15T12:30:00+00:00"
        result = parse_ais_timestamp(ts)
        assert result is not None
        assert result.year == 2026

    def test_none_input(self):
        """None input should return None."""
        assert parse_ais_timestamp(None) is None

    def test_garbage_input(self):
        """Invalid input should return None."""
        assert parse_ais_timestamp("not a date") is None
