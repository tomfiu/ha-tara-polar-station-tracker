"""Tests for sensor and binary sensor entity value logic."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.tara_polar_station_tracker.binary_sensor import (
    BINARY_SENSOR_DESCRIPTIONS,
)
from custom_components.tara_polar_station_tracker.coordinator import (
    TaraPolarStationCoordinator,
)
from custom_components.tara_polar_station_tracker.sensor import SENSOR_DESCRIPTIONS


def _make_coordinator(data=None) -> TaraPolarStationCoordinator:
    """Return a coordinator with pre-populated data."""
    hass = MagicMock()
    hass.bus = MagicMock()
    store = MagicMock()
    store.async_load = AsyncMock(return_value=None)
    store.async_save = AsyncMock()
    coord = TaraPolarStationCoordinator(
        hass=hass,
        api_key="test",
        poll_interval=15,
        home_lat=50.0,
        home_lon=14.0,
        departure_date="2026-01-01",
        store=store,
    )
    coord.data = data
    return coord


_FULL_DATA = {
    "latitude": 79.332,
    "longitude": -23.992,
    "speed": 0.3,
    "course": 45.0,
    "heading": 511,
    "nav_status": 0,
    "timestamp": None,
    "distance_from_home": 4200.5,
    "distance_to_north_pole": 1180.0,
    "bearing_from_home": 12.3,
    "bearing_compass": "NNE",
    "in_arctic_circle": True,
    "in_polar_day": True,
    "in_polar_night": False,
    "solar_elevation": 15.2,
    "local_sunrise": None,
    "local_sunset": None,
    "stationary": True,
    "days_since_departure": 200,
    "mission_phase": "Drifting",
    "track_history": [],
}


class TestSensorDescriptionValueFns:
    """Test the value_fn lambdas in SENSOR_DESCRIPTIONS."""

    def _get_desc(self, key: str):
        for d in SENSOR_DESCRIPTIONS:
            if d.key == key:
                return d
        raise KeyError(f"No sensor description with key={key!r}")

    def test_latitude_value_fn(self):
        desc = self._get_desc("latitude")
        assert desc.value_fn(_FULL_DATA) == pytest.approx(79.332)

    def test_longitude_value_fn(self):
        desc = self._get_desc("longitude")
        assert desc.value_fn(_FULL_DATA) == pytest.approx(-23.992)

    def test_speed_value_fn(self):
        desc = self._get_desc("speed")
        assert desc.value_fn(_FULL_DATA) == pytest.approx(0.3)

    def test_course_value_fn(self):
        desc = self._get_desc("course")
        assert desc.value_fn(_FULL_DATA) == pytest.approx(45.0)

    def test_distance_from_home_value_fn(self):
        desc = self._get_desc("distance_from_home")
        assert desc.value_fn(_FULL_DATA) == pytest.approx(4200.5)

    def test_distance_to_north_pole_value_fn(self):
        desc = self._get_desc("distance_to_north_pole")
        assert desc.value_fn(_FULL_DATA) == pytest.approx(1180.0)

    def test_bearing_from_home_value_fn(self):
        desc = self._get_desc("bearing_from_home")
        assert desc.value_fn(_FULL_DATA) == pytest.approx(12.3)

    def test_days_since_departure_value_fn(self):
        desc = self._get_desc("days_since_departure")
        assert desc.value_fn(_FULL_DATA) == 200

    def test_solar_elevation_value_fn(self):
        desc = self._get_desc("solar_elevation")
        assert desc.value_fn(_FULL_DATA) == pytest.approx(15.2)

    def test_mission_phase_value_fn(self):
        desc = self._get_desc("mission_phase")
        assert desc.value_fn(_FULL_DATA) == "Drifting"

    def test_value_fn_returns_none_when_key_missing(self):
        """Value function should return None for missing keys."""
        desc = self._get_desc("latitude")
        assert desc.value_fn({}) is None

    def test_bearing_extra_attrs_fn(self):
        """bearing_from_home should expose compass direction as extra attribute."""
        desc = self._get_desc("bearing_from_home")
        assert desc.extra_attrs_fn is not None
        attrs = desc.extra_attrs_fn(_FULL_DATA)
        assert attrs == {"compass_direction": "NNE"}

    def test_extra_attrs_fn_is_none_for_most_sensors(self):
        """Sensors without extra attributes should have extra_attrs_fn=None."""
        for desc in SENSOR_DESCRIPTIONS:
            if desc.key != "bearing_from_home":
                assert desc.extra_attrs_fn is None, (
                    f"Sensor {desc.key!r} unexpectedly has extra_attrs_fn"
                )

    def test_all_sensor_keys_are_unique(self):
        """Each sensor description must have a unique key."""
        keys = [d.key for d in SENSOR_DESCRIPTIONS]
        assert len(keys) == len(set(keys))


class TestBinarySensorDescriptionValueFns:
    """Test the value_fn lambdas in BINARY_SENSOR_DESCRIPTIONS."""

    def _get_desc(self, key: str):
        for d in BINARY_SENSOR_DESCRIPTIONS:
            if d.key == key:
                return d
        raise KeyError(f"No binary sensor description with key={key!r}")

    def test_in_arctic_circle_true(self):
        desc = self._get_desc("in_arctic_circle")
        assert desc.value_fn(_FULL_DATA) is True

    def test_in_arctic_circle_false(self):
        desc = self._get_desc("in_arctic_circle")
        assert desc.value_fn({**_FULL_DATA, "in_arctic_circle": False}) is False

    def test_in_polar_day_true(self):
        desc = self._get_desc("in_polar_day")
        assert desc.value_fn(_FULL_DATA) is True

    def test_in_polar_night_false(self):
        desc = self._get_desc("in_polar_night")
        assert desc.value_fn(_FULL_DATA) is False

    def test_stationary_true(self):
        desc = self._get_desc("stationary")
        assert desc.value_fn(_FULL_DATA) is True

    def test_stationary_false(self):
        desc = self._get_desc("stationary")
        assert desc.value_fn({**_FULL_DATA, "stationary": False}) is False

    def test_value_fn_returns_none_when_key_missing(self):
        """Value function should return None for missing keys."""
        desc = self._get_desc("in_arctic_circle")
        assert desc.value_fn({}) is None

    def test_all_binary_sensor_keys_are_unique(self):
        """Each binary sensor description must have a unique key."""
        keys = [d.key for d in BINARY_SENSOR_DESCRIPTIONS]
        assert len(keys) == len(set(keys))

    def test_expected_binary_sensors_present(self):
        """All four expected binary sensors should be described."""
        keys = {d.key for d in BINARY_SENSOR_DESCRIPTIONS}
        assert keys == {"in_arctic_circle", "in_polar_day", "in_polar_night", "stationary"}
