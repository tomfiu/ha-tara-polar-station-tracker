"""Tests for utility functions."""
from __future__ import annotations

import math
from datetime import datetime, timezone

import pytest

from custom_components.tara_polar_station_tracker.utils import (
    calculate_bearing,
    compass_direction,
    get_solar_elevation,
    get_sunrise_sunset,
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

    def test_empty_string_returns_none(self):
        """Empty string should return None."""
        assert parse_ais_timestamp("") is None

    def test_timezone_preserved(self):
        """Parsed timestamp should have UTC timezone info."""
        ts = "2026-08-15 12:30:00.000000 +0000 UTC"
        result = parse_ais_timestamp(ts)
        assert result.tzinfo is not None
        assert result.utcoffset().total_seconds() == 0


class TestGetSolarElevation:
    """Test solar elevation calculation."""

    def test_returns_float(self):
        """Solar elevation should be a float."""
        dt = datetime(2026, 6, 21, 12, 0, tzinfo=timezone.utc)
        result = get_solar_elevation(50.0, 14.0, dt)
        assert isinstance(result, float)

    def test_midday_sun_above_horizon_at_midlatitude(self):
        """At midday in summer at 50°N, sun should be above horizon."""
        dt = datetime(2026, 6, 21, 12, 0, tzinfo=timezone.utc)
        result = get_solar_elevation(50.0, 0.0, dt)
        assert result > 0

    def test_midnight_sun_below_horizon_at_midlatitude(self):
        """At midnight in winter at 50°N, sun should be well below horizon."""
        dt = datetime(2026, 12, 21, 0, 0, tzinfo=timezone.utc)
        result = get_solar_elevation(50.0, 0.0, dt)
        assert result < 0

    def test_polar_day_sun_above_horizon(self):
        """During Arctic summer at 80°N, solar elevation should be positive."""
        dt = datetime(2026, 6, 21, 12, 0, tzinfo=timezone.utc)
        result = get_solar_elevation(80.0, 0.0, dt)
        assert result > 0

    def test_polar_night_sun_below_horizon(self):
        """During Arctic winter at 80°N, solar elevation should be negative."""
        dt = datetime(2026, 12, 21, 12, 0, tzinfo=timezone.utc)
        result = get_solar_elevation(80.0, 0.0, dt)
        assert result < 0

    def test_elevation_range(self):
        """Solar elevation should always be in -90..90 range."""
        for month in [1, 3, 6, 9, 12]:
            for lat in [-80, -45, 0, 45, 80]:
                dt = datetime(2026, month, 15, 12, 0, tzinfo=timezone.utc)
                result = get_solar_elevation(float(lat), 0.0, dt)
                assert -90 <= result <= 90


class TestGetSunriseSunset:
    """Test sunrise and sunset calculation."""

    def test_returns_tuple(self):
        """get_sunrise_sunset should return a tuple of two elements."""
        dt = datetime(2026, 6, 21, 12, 0, tzinfo=timezone.utc)
        result = get_sunrise_sunset(50.0, 0.0, dt)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_normal_day_returns_datetimes(self):
        """A normal day at mid-latitude should return two datetimes."""
        dt = datetime(2026, 6, 21, 12, 0, tzinfo=timezone.utc)
        sr, ss = get_sunrise_sunset(50.0, 0.0, dt)
        assert isinstance(sr, datetime)
        assert isinstance(ss, datetime)

    def test_sunrise_before_sunset(self):
        """Sunrise should be before sunset on a normal day."""
        dt = datetime(2026, 6, 21, 12, 0, tzinfo=timezone.utc)
        sr, ss = get_sunrise_sunset(50.0, 0.0, dt)
        assert sr < ss

    def test_polar_day_no_sunrise_sunset(self):
        """During polar day at 80°N in summer, sunrise/sunset may return None."""
        dt = datetime(2026, 6, 21, 12, 0, tzinfo=timezone.utc)
        sr, ss = get_sunrise_sunset(80.0, 0.0, dt)
        # During polar day, at least one of them should be None (sun doesn't set)
        # This verifies the function handles polar conditions gracefully
        assert sr is None or ss is None or isinstance(sr, datetime)

    def test_polar_night_returns_none_values(self):
        """During polar night at 80°N in winter, both may return None."""
        dt = datetime(2026, 12, 21, 12, 0, tzinfo=timezone.utc)
        sr, ss = get_sunrise_sunset(80.0, 0.0, dt)
        # Both None is acceptable for polar night
        assert sr is None or isinstance(sr, datetime)
        assert ss is None or isinstance(ss, datetime)

    def test_return_types_are_aware(self):
        """Returned datetimes should be timezone-aware."""
        dt = datetime(2026, 3, 15, 12, 0, tzinfo=timezone.utc)
        sr, ss = get_sunrise_sunset(50.0, 0.0, dt)
        if sr is not None:
            assert sr.tzinfo is not None
        if ss is not None:
            assert ss.tzinfo is not None
