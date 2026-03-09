"""Tests for the Tara Polar Station coordinator."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.tara_polar_station_tracker.coordinator import (
    TaraPolarStationCoordinator,
)


class TestParseNullschoolTrack:
    """Test the _parse_nullschool_track static method."""

    # Columnar payload format: [headers, rows]
    _HEADERS = ["timestamp", "lon", "lat", "track", "speed"]
    _TS = 1773042605  # 2026-03-09 UTC

    def _payload(self, rows):
        return [self._HEADERS, rows]

    def test_parse_valid_payload(self):
        """Parse a well-formed columnar payload and return the last row."""
        payload = self._payload([
            [self._TS - 3600, 15.0, 78.0, 90, 0],
            [self._TS, -1.608, 49.647, 0, 0],
        ])
        result = TaraPolarStationCoordinator._parse_nullschool_track(payload)
        assert result is not None
        assert result["latitude"] == pytest.approx(49.647)
        assert result["longitude"] == pytest.approx(-1.608)
        assert result["speed"] == pytest.approx(0.0)
        assert result["course"] == pytest.approx(0.0)
        assert result["heading"] is None
        assert result["nav_status"] is None

    def test_timestamp_converted_to_datetime(self):
        """Timestamp field should be a timezone-aware UTC datetime."""
        payload = self._payload([[self._TS, 0.0, 80.0, 45, 5]])
        result = TaraPolarStationCoordinator._parse_nullschool_track(payload)
        assert isinstance(result["timestamp"], datetime)
        assert result["timestamp"].tzinfo is not None
        assert result["timestamp"] == datetime.fromtimestamp(
            self._TS, tz=timezone.utc
        )

    def test_most_recent_row_used(self):
        """The last row in the data array should be used."""
        payload = self._payload([
            [self._TS - 7200, 10.0, 70.0, 0, 3],
            [self._TS - 3600, 11.0, 71.0, 0, 2],
            [self._TS, 12.0, 72.0, 0, 1],
        ])
        result = TaraPolarStationCoordinator._parse_nullschool_track(payload)
        assert result["latitude"] == pytest.approx(72.0)
        assert result["longitude"] == pytest.approx(12.0)

    def test_column_order_independent(self):
        """Parser should use header names, not fixed positions."""
        # Swap lat and lon vs usual order
        payload = [
            ["timestamp", "lat", "lon", "track", "speed"],
            [[self._TS, 75.0, 20.0, 90, 4]],
        ]
        result = TaraPolarStationCoordinator._parse_nullschool_track(payload)
        assert result["latitude"] == pytest.approx(75.0)
        assert result["longitude"] == pytest.approx(20.0)

    def test_returns_none_for_empty_rows(self):
        """Empty data array should return None."""
        payload = self._payload([])
        result = TaraPolarStationCoordinator._parse_nullschool_track(payload)
        assert result is None

    def test_returns_none_for_wrong_format(self):
        """A plain dict payload should return None."""
        result = TaraPolarStationCoordinator._parse_nullschool_track(
            {"positions": []}
        )
        assert result is None

    def test_returns_none_for_non_list(self):
        """A string payload should return None."""
        result = TaraPolarStationCoordinator._parse_nullschool_track("bad")
        assert result is None


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
        store = MagicMock()
        store.async_load = AsyncMock(return_value=None)
        store.async_save = AsyncMock()
        coord = TaraPolarStationCoordinator(
            hass=hass,
            api_key="test",
            poll_interval=15,
            home_lat=home_lat,
            home_lon=home_lon,
            departure_date=departure_date,
            store=store,
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


class TestCaching:
    """Test persistent position caching."""

    def _make_coordinator(self, store=None):
        """Create a coordinator with an optional custom store mock."""
        hass = MagicMock()
        hass.bus = MagicMock()
        if store is None:
            store = MagicMock()
            store.async_load = AsyncMock(return_value=None)
            store.async_save = AsyncMock()
        return TaraPolarStationCoordinator(
            hass=hass,
            api_key="test",
            poll_interval=15,
            home_lat=50.0,
            home_lon=14.0,
            departure_date="2026-07-01",
            store=store,
        )

    @pytest.mark.asyncio
    async def test_load_cache_populates_previous_data(self):
        """Loading a valid cache should set _previous_data."""
        cached = {
            "latitude": 79.332,
            "longitude": -23.992,
            "speed": 0.3,
            "course": 45.0,
            "heading": 511,
            "nav_status": 0,
            "timestamp": "2026-08-15 12:30:00.000000 +0000 UTC",
        }
        store = MagicMock()
        store.async_load = AsyncMock(return_value=cached)
        store.async_save = AsyncMock()

        coord = self._make_coordinator(store=store)
        await coord._load_cache()

        assert coord._previous_data is not None
        assert coord._previous_data["latitude"] == pytest.approx(79.332)
        assert coord._previous_data["in_arctic_circle"] is True
        store.async_load.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_load_cache_none_leaves_previous_data_empty(self):
        """When no cache exists, _previous_data should remain None."""
        store = MagicMock()
        store.async_load = AsyncMock(return_value=None)
        store.async_save = AsyncMock()

        coord = self._make_coordinator(store=store)
        await coord._load_cache()

        assert coord._previous_data is None

    @pytest.mark.asyncio
    async def test_save_cache_stores_raw_data(self):
        """_save_cache should persist raw telemetry."""
        store = MagicMock()
        store.async_load = AsyncMock(return_value=None)
        store.async_save = AsyncMock()

        coord = self._make_coordinator(store=store)
        raw = {
            "latitude": 79.332,
            "longitude": -23.992,
            "speed": 0.3,
            "course": 45.0,
            "heading": 511,
            "nav_status": 0,
            "timestamp": "2026-08-15T12:30:00+00:00",
        }
        await coord._save_cache(raw)

        store.async_save.assert_awaited_once()
        saved = store.async_save.call_args[0][0]
        assert saved["latitude"] == pytest.approx(79.332)
        assert saved["longitude"] == pytest.approx(-23.992)

    @pytest.mark.asyncio
    async def test_save_cache_converts_datetime_timestamp(self):
        """When timestamp is a datetime, it should be serialised as ISO string."""
        store = MagicMock()
        store.async_load = AsyncMock(return_value=None)
        store.async_save = AsyncMock()

        coord = self._make_coordinator(store=store)
        ts = datetime(2026, 8, 15, 12, 30, tzinfo=timezone.utc)
        raw = {
            "latitude": 70.0,
            "longitude": 0.0,
            "speed": 0.0,
            "course": 0.0,
            "heading": None,
            "nav_status": None,
            "timestamp": ts,
        }
        await coord._save_cache(raw)

        saved = store.async_save.call_args[0][0]
        assert saved["timestamp"] == ts.isoformat()

    def test_initial_interval_is_fast(self):
        """Coordinator should start with the fast poll interval."""
        coord = self._make_coordinator()
        from datetime import timedelta

        from custom_components.tara_polar_station_tracker.const import (
            FAST_POLL_INTERVAL,
        )

        assert coord.update_interval == timedelta(minutes=FAST_POLL_INTERVAL)
