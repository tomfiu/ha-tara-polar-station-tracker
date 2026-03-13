"""Tests for the Tara Polar Station coordinator."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from custom_components.tara_polar_station_tracker.const import (
    EVENT_ENTERED_ARCTIC,
    EVENT_ENTERED_POLAR_NIGHT,
    EVENT_POSITION_UPDATED,
    EVENT_RESUMED_TRANSIT,
    EVENT_STATIONARY,
    FAST_POLL_INTERVAL,
)
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
        assert coord.update_interval == timedelta(minutes=FAST_POLL_INTERVAL)

    @pytest.mark.asyncio
    async def test_load_cache_exception_is_swallowed(self):
        """A store load failure should not raise — _previous_data stays None."""
        store = MagicMock()
        store.async_load = AsyncMock(side_effect=RuntimeError("disk error"))
        store.async_save = AsyncMock()

        coord = self._make_coordinator(store=store)
        await coord._load_cache()

        assert coord._previous_data is None

    @pytest.mark.asyncio
    async def test_save_cache_exception_is_swallowed(self):
        """A store save failure should not raise."""
        store = MagicMock()
        store.async_load = AsyncMock(return_value=None)
        store.async_save = AsyncMock(side_effect=OSError("write error"))

        coord = self._make_coordinator(store=store)
        raw = {
            "latitude": 70.0,
            "longitude": 0.0,
            "speed": 0.0,
            "course": 0.0,
            "heading": None,
            "nav_status": None,
            "timestamp": None,
        }
        # Should not raise
        await coord._save_cache(raw)


class TestParseDatalastic:
    """Test the _parse_datalastic static method."""

    def test_parse_valid_response(self):
        """A complete Datalastic payload should be parsed correctly."""
        payload = {
            "data": {
                "latitude": 79.332,
                "longitude": -23.992,
                "speed": 0.3,
                "course": 45.0,
                "heading": 511,
                "navigational_status": 0,
                "timestamp": "2026-08-15T12:30:00+00:00",
            }
        }
        result = TaraPolarStationCoordinator._parse_datalastic(payload)
        assert result is not None
        assert result["latitude"] == pytest.approx(79.332)
        assert result["longitude"] == pytest.approx(-23.992)
        assert result["speed"] == pytest.approx(0.3)
        assert result["course"] == pytest.approx(45.0)
        assert result["heading"] == 511
        assert result["nav_status"] == 0
        assert result["timestamp"] == "2026-08-15T12:30:00+00:00"

    def test_returns_none_when_data_missing(self):
        """Missing 'data' key should return None."""
        result = TaraPolarStationCoordinator._parse_datalastic({})
        assert result is None

    def test_returns_none_when_data_is_none(self):
        """data=None should return None."""
        result = TaraPolarStationCoordinator._parse_datalastic({"data": None})
        assert result is None

    def test_returns_none_when_latitude_missing(self):
        """Missing latitude should return None."""
        payload = {"data": {"longitude": -23.992}}
        result = TaraPolarStationCoordinator._parse_datalastic(payload)
        assert result is None

    def test_returns_none_when_longitude_missing(self):
        """Missing longitude should return None."""
        payload = {"data": {"latitude": 79.332}}
        result = TaraPolarStationCoordinator._parse_datalastic(payload)
        assert result is None

    def test_optional_fields_default_to_zero(self):
        """Missing speed and course should default to 0.0."""
        payload = {
            "data": {
                "latitude": 70.0,
                "longitude": 10.0,
            }
        }
        result = TaraPolarStationCoordinator._parse_datalastic(payload)
        assert result is not None
        assert result["speed"] == pytest.approx(0.0)
        assert result["course"] == pytest.approx(0.0)

    def test_optional_fields_none_when_absent(self):
        """Missing heading and nav_status should be None."""
        payload = {
            "data": {
                "latitude": 70.0,
                "longitude": 10.0,
            }
        }
        result = TaraPolarStationCoordinator._parse_datalastic(payload)
        assert result is not None
        assert result["heading"] is None
        assert result["nav_status"] is None


class TestFireEvents:
    """Test the _fire_events method."""

    def _make_coordinator(self) -> TaraPolarStationCoordinator:
        hass = MagicMock()
        hass.bus = MagicMock()
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

    def _data(self, **overrides) -> dict:
        base = {
            "latitude": 79.0,
            "longitude": -20.0,
            "speed": 0.3,
            "timestamp": None,
            "distance_to_north_pole": 1200.0,
            "in_arctic_circle": True,
            "in_polar_night": False,
            "stationary": True,
        }
        base.update(overrides)
        return base

    def test_position_updated_always_fired(self):
        """EVENT_POSITION_UPDATED should fire on every call."""
        coord = self._make_coordinator()
        coord._fire_events(self._data())
        assert coord.hass.bus.async_fire.call_count == 1
        assert coord.hass.bus.async_fire.call_args[0][0] == EVENT_POSITION_UPDATED

    def test_position_updated_always_fired_with_previous(self):
        """EVENT_POSITION_UPDATED fires even when previous data exists."""
        coord = self._make_coordinator()
        coord._previous_data = self._data()
        coord._fire_events(self._data())
        fired_events = [c[0][0] for c in coord.hass.bus.async_fire.call_args_list]
        assert EVENT_POSITION_UPDATED in fired_events

    def test_no_transition_events_without_previous_data(self):
        """Only position updated fires when there is no previous data."""
        coord = self._make_coordinator()
        coord._fire_events(self._data())
        assert coord.hass.bus.async_fire.call_count == 1

    def test_arctic_entry_event(self):
        """Entering arctic circle should fire EVENT_ENTERED_ARCTIC."""
        coord = self._make_coordinator()
        coord._previous_data = self._data(in_arctic_circle=False)
        coord._fire_events(self._data(in_arctic_circle=True))
        fired = [c[0][0] for c in coord.hass.bus.async_fire.call_args_list]
        assert EVENT_ENTERED_ARCTIC in fired

    def test_no_arctic_event_when_already_in_arctic(self):
        """No arctic event when vessel was already in arctic circle."""
        coord = self._make_coordinator()
        coord._previous_data = self._data(in_arctic_circle=True)
        coord._fire_events(self._data(in_arctic_circle=True))
        fired = [c[0][0] for c in coord.hass.bus.async_fire.call_args_list]
        assert EVENT_ENTERED_ARCTIC not in fired

    def test_polar_night_entry_event(self):
        """Entering polar night should fire EVENT_ENTERED_POLAR_NIGHT."""
        coord = self._make_coordinator()
        coord._previous_data = self._data(in_polar_night=False)
        coord._fire_events(self._data(in_polar_night=True))
        fired = [c[0][0] for c in coord.hass.bus.async_fire.call_args_list]
        assert EVENT_ENTERED_POLAR_NIGHT in fired

    def test_stationary_event(self):
        """Becoming stationary should fire EVENT_STATIONARY."""
        coord = self._make_coordinator()
        coord._previous_data = self._data(stationary=False)
        coord._fire_events(self._data(stationary=True))
        fired = [c[0][0] for c in coord.hass.bus.async_fire.call_args_list]
        assert EVENT_STATIONARY in fired

    def test_resumed_transit_event(self):
        """Resuming transit (was stationary, now moving) fires EVENT_RESUMED_TRANSIT."""
        coord = self._make_coordinator()
        coord._previous_data = self._data(stationary=True)
        coord._fire_events(self._data(stationary=False))
        fired = [c[0][0] for c in coord.hass.bus.async_fire.call_args_list]
        assert EVENT_RESUMED_TRANSIT in fired

    def test_no_resumed_transit_when_was_moving(self):
        """No resumed transit event when vessel was already moving."""
        coord = self._make_coordinator()
        coord._previous_data = self._data(stationary=False)
        coord._fire_events(self._data(stationary=False))
        fired = [c[0][0] for c in coord.hass.bus.async_fire.call_args_list]
        assert EVENT_RESUMED_TRANSIT not in fired

    def test_event_payload_contains_position(self):
        """Event payload should include latitude and longitude."""
        coord = self._make_coordinator()
        data = self._data(latitude=79.5, longitude=-24.1)
        coord._fire_events(data)
        payload = coord.hass.bus.async_fire.call_args[0][1]
        assert payload["latitude"] == pytest.approx(79.5)
        assert payload["longitude"] == pytest.approx(-24.1)


class TestEmptyData:
    """Test the _empty_data method."""

    def _make_coordinator(self, departure_date="2026-07-01"):
        hass = MagicMock()
        hass.bus = MagicMock()
        store = MagicMock()
        store.async_load = AsyncMock(return_value=None)
        store.async_save = AsyncMock()
        return TaraPolarStationCoordinator(
            hass=hass,
            api_key="test",
            poll_interval=15,
            home_lat=50.0,
            home_lon=14.0,
            departure_date=departure_date,
            store=store,
        )

    def test_empty_data_keys(self):
        """_empty_data should include all expected keys."""
        coord = self._make_coordinator()
        data = coord._empty_data()
        for key in [
            "latitude", "longitude", "speed", "course", "heading", "nav_status",
            "timestamp", "distance_from_home", "distance_to_north_pole",
            "bearing_from_home", "bearing_compass", "in_arctic_circle",
            "in_polar_day", "in_polar_night", "solar_elevation", "local_sunrise",
            "local_sunset", "stationary", "days_since_departure", "mission_phase",
            "track_history",
        ]:
            assert key in data, f"Missing key: {key}"

    def test_empty_data_position_is_none(self):
        """Position fields should be None."""
        coord = self._make_coordinator()
        data = coord._empty_data()
        assert data["latitude"] is None
        assert data["longitude"] is None

    def test_empty_data_booleans_are_false(self):
        """Boolean flags should default to False."""
        coord = self._make_coordinator()
        data = coord._empty_data()
        assert data["in_arctic_circle"] is False
        assert data["in_polar_day"] is False
        assert data["in_polar_night"] is False
        assert data["stationary"] is False

    def test_empty_data_track_history_empty_list(self):
        """track_history should be an empty list."""
        coord = self._make_coordinator()
        data = coord._empty_data()
        assert data["track_history"] == []

    def test_empty_data_pre_departure_phase(self):
        """Before departure, phase should be Pre-departure."""
        coord = self._make_coordinator(departure_date="2099-01-01")
        data = coord._empty_data()
        assert data["mission_phase"] == "Pre-departure"
        assert data["days_since_departure"] == 0

    def test_empty_data_invalid_departure_date(self):
        """Invalid departure date should yield None days and Pre-departure phase."""
        coord = self._make_coordinator(departure_date="not-a-date")
        data = coord._empty_data()
        assert data["days_since_departure"] is None
        assert data["mission_phase"] == "Pre-departure"


class TestNullschoolTrackHistory:
    """Test that _parse_nullschool_track produces track_history."""

    _HEADERS = ["timestamp", "lon", "lat", "track", "speed"]
    _TS = 1773042605

    def _payload(self, rows):
        return [self._HEADERS, rows]

    def test_track_history_included(self):
        """track_history should contain all rows."""
        payload = self._payload([
            [self._TS - 3600, 10.0, 70.0, 0, 2],
            [self._TS, 11.0, 71.0, 45, 3],
        ])
        result = TaraPolarStationCoordinator._parse_nullschool_track(payload)
        assert result is not None
        assert "track_history" in result
        assert len(result["track_history"]) == 2

    def test_track_history_point_structure(self):
        """Each track history entry should have latitude, longitude, and timestamp."""
        payload = self._payload([[self._TS, 15.0, 78.0, 90, 1]])
        result = TaraPolarStationCoordinator._parse_nullschool_track(payload)
        assert result is not None
        assert len(result["track_history"]) == 1
        point = result["track_history"][0]
        assert "latitude" in point
        assert "longitude" in point
        assert "timestamp" in point
        assert point["latitude"] == pytest.approx(78.0)
        assert point["longitude"] == pytest.approx(15.0)

    def test_track_history_timestamps_are_iso_strings(self):
        """Track history timestamps should be ISO-formatted strings."""
        payload = self._payload([[self._TS, 0.0, 80.0, 0, 0]])
        result = TaraPolarStationCoordinator._parse_nullschool_track(payload)
        assert result is not None
        ts_str = result["track_history"][0]["timestamp"]
        assert isinstance(ts_str, str)
        # Should parse back to the original UTC time
        parsed = datetime.fromisoformat(ts_str)
        assert parsed == datetime.fromtimestamp(self._TS, tz=timezone.utc)

    def test_track_history_order_preserved(self):
        """Track history should preserve row order (oldest first)."""
        payload = self._payload([
            [self._TS - 7200, 10.0, 70.0, 0, 1],
            [self._TS - 3600, 11.0, 71.0, 0, 2],
            [self._TS, 12.0, 72.0, 0, 3],
        ])
        result = TaraPolarStationCoordinator._parse_nullschool_track(payload)
        assert result is not None
        lats = [p["latitude"] for p in result["track_history"]]
        assert lats == [70.0, 71.0, 72.0]


class TestComputeDerivedExtra:
    """Additional tests for _compute_derived edge cases."""

    def _make_coordinator(self, departure_date="2026-01-01"):
        hass = MagicMock()
        hass.bus = MagicMock()
        store = MagicMock()
        store.async_load = AsyncMock(return_value=None)
        store.async_save = AsyncMock()
        return TaraPolarStationCoordinator(
            hass=hass,
            api_key="test",
            poll_interval=15,
            home_lat=50.0,
            home_lon=14.0,
            departure_date=departure_date,
            store=store,
        )

    def _raw(self, **overrides) -> dict:
        base = {
            "latitude": 70.0,
            "longitude": 0.0,
            "speed": 0.0,
            "course": 90.0,
            "heading": None,
            "nav_status": None,
            "timestamp": None,
        }
        base.update(overrides)
        return base

    def test_bearing_compass_present(self):
        """bearing_compass should be a non-empty string when position is known."""
        coord = self._make_coordinator()
        result = coord._compute_derived(self._raw())
        assert isinstance(result["bearing_compass"], str)
        assert len(result["bearing_compass"]) > 0

    def test_days_since_departure_positive(self):
        """Past departure date should yield a positive integer."""
        coord = self._make_coordinator(departure_date="2020-01-01")
        result = coord._compute_derived(self._raw())
        assert isinstance(result["days_since_departure"], int)
        assert result["days_since_departure"] > 0

    def test_days_since_departure_invalid_date(self):
        """Invalid departure date should yield None."""
        coord = self._make_coordinator(departure_date="invalid")
        result = coord._compute_derived(self._raw())
        assert result["days_since_departure"] is None

    def test_stationary_at_exact_threshold(self):
        """Speed exactly at STATIONARY_SPEED_THRESHOLD (0.5) is not stationary."""
        from custom_components.tara_polar_station_tracker.const import (
            STATIONARY_SPEED_THRESHOLD,
        )
        coord = self._make_coordinator()
        result = coord._compute_derived(self._raw(speed=STATIONARY_SPEED_THRESHOLD))
        assert result["stationary"] is False

    def test_stationary_below_threshold(self):
        """Speed below threshold (0.4) should be stationary."""
        coord = self._make_coordinator()
        result = coord._compute_derived(self._raw(speed=0.4))
        assert result["stationary"] is True

    def test_solar_elevation_is_float(self):
        """solar_elevation should be a float when position is known."""
        coord = self._make_coordinator()
        result = coord._compute_derived(
            self._raw(
                latitude=70.0,
                longitude=0.0,
                timestamp="2026-06-21 12:00:00.000000 +0000 UTC",
            )
        )
        assert isinstance(result["solar_elevation"], float)

    def test_timestamp_parsed_to_datetime(self):
        """Timestamp string should be converted to a datetime object."""
        coord = self._make_coordinator()
        result = coord._compute_derived(
            self._raw(timestamp="2026-08-15 12:00:00.000000 +0000 UTC")
        )
        assert isinstance(result["timestamp"], datetime)
        assert result["timestamp"].tzinfo is not None

    def test_distance_from_home_is_positive(self):
        """Distance from home should be a positive number when position differs."""
        coord = self._make_coordinator()
        result = coord._compute_derived(self._raw(latitude=70.0, longitude=0.0))
        assert result["distance_from_home"] > 0

    def test_arctic_boundary_exactly_at_threshold(self):
        """Position exactly at ARCTIC_CIRCLE_LATITUDE should be in arctic circle."""
        from custom_components.tara_polar_station_tracker.const import (
            ARCTIC_CIRCLE_LATITUDE,
        )
        coord = self._make_coordinator()
        result = coord._compute_derived(self._raw(latitude=ARCTIC_CIRCLE_LATITUDE))
        assert result["in_arctic_circle"] is True

    def test_just_below_arctic_boundary(self):
        """Position just below ARCTIC_CIRCLE_LATITUDE should not be in arctic circle."""
        from custom_components.tara_polar_station_tracker.const import (
            ARCTIC_CIRCLE_LATITUDE,
        )
        coord = self._make_coordinator()
        result = coord._compute_derived(
            self._raw(latitude=ARCTIC_CIRCLE_LATITUDE - 0.001)
        )
        assert result["in_arctic_circle"] is False
