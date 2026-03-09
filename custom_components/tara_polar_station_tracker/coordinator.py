"""DataUpdateCoordinator for Tara Polar Station Tracker."""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    AISSTREAM_WS_URL,
    ARCTIC_CIRCLE_LATITUDE,
    DOMAIN,
    EVENT_ENTERED_ARCTIC,
    EVENT_ENTERED_POLAR_NIGHT,
    EVENT_POSITION_UPDATED,
    EVENT_RESUMED_TRANSIT,
    EVENT_STATIONARY,
    FAST_POLL_INTERVAL,
    NORTH_POLE_LATITUDE,
    NORTH_POLE_LONGITUDE,
    STATIONARY_SPEED_THRESHOLD,
    TARA_MMSI,
)
from .utils import (
    calculate_bearing,
    compass_direction,
    get_solar_elevation,
    get_sunrise_sunset,
    haversine_distance,
    is_polar_day,
    is_polar_night,
    parse_ais_timestamp,
)

_LOGGER = logging.getLogger(__name__)

WS_TIMEOUT = 90  # seconds to wait for a position report


class TaraPolarStationCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to manage fetching Tara Polar Station data."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_key: str,
        poll_interval: int,
        home_lat: float,
        home_lon: float,
        departure_date: str,
        store: Store,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=FAST_POLL_INTERVAL),
        )
        self._api_key = api_key
        self._normal_interval = timedelta(minutes=poll_interval)
        self._fast_interval = timedelta(minutes=FAST_POLL_INTERVAL)
        self._home_lat = home_lat
        self._home_lon = home_lon
        self._departure_date = departure_date
        self._store = store
        self._previous_data: dict[str, Any] | None = None
        self._cache_loaded = False

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from AISStream and compute derived values."""
        # On first run, load any cached position from disk.
        if not self._cache_loaded:
            self._cache_loaded = True
            await self._load_cache()

        raw = await self._fetch_ais_data()

        if raw is not None:
            data = self._compute_derived(raw)
            self._fire_events(data)
            self._previous_data = data
            _LOGGER.debug("Updated telemetry: %s", data)

            # Persist raw position data so it survives restarts.
            await self._save_cache(raw)

            # Switch to normal polling now that we have data.
            if self.update_interval != self._normal_interval:
                _LOGGER.debug(
                    "Switching to normal poll interval (%s)",
                    self._normal_interval,
                )
                self.update_interval = self._normal_interval

            return data

        if self._previous_data is not None:
            # Re-derive time-dependent values (solar, polar day/night, days)
            # using the last known position.
            _LOGGER.debug("No new AIS data, recomputing from last known position")
            data = self._compute_derived(self._previous_data)
            self._previous_data = data

            # If we have cached data, use the normal interval.
            if self.update_interval != self._normal_interval:
                self.update_interval = self._normal_interval

            return data

        # No data yet — return empty defaults so setup succeeds.
        # Keep the fast poll interval to retry sooner.
        _LOGGER.warning(
            "No AIS data received yet for Tara Polar Station; "
            "sensors will update once a position report is available"
        )
        return self._empty_data()

    def _empty_data(self) -> dict[str, Any]:
        """Return a default data dict — computes what it can without AIS position."""
        now = datetime.now(timezone.utc)

        # Days since departure is independent of AIS data
        try:
            departure = datetime.strptime(
                self._departure_date, "%Y-%m-%d"
            ).replace(tzinfo=timezone.utc)
            delta = now - departure
            days = max(0, delta.days)
        except (ValueError, TypeError):
            days = None

        if days is None or days == 0:
            phase = "Pre-departure"
        else:
            phase = "Drifting"  # assume drifting when no position data

        return {
            "latitude": None,
            "longitude": None,
            "speed": None,
            "course": None,
            "heading": None,
            "nav_status": None,
            "timestamp": None,
            "distance_from_home": None,
            "distance_to_north_pole": None,
            "bearing_from_home": None,
            "bearing_compass": None,
            "in_arctic_circle": False,
            "in_polar_day": False,
            "in_polar_night": False,
            "solar_elevation": None,
            "local_sunrise": None,
            "local_sunset": None,
            "stationary": False,
            "days_since_departure": days,
            "mission_phase": phase,
        }

    async def _load_cache(self) -> None:
        """Load the last known position from persistent storage."""
        try:
            cached: dict[str, Any] | None = await self._store.async_load()
        except Exception:
            _LOGGER.warning("Failed to load cached position data", exc_info=True)
            return

        if cached and cached.get("latitude") is not None:
            _LOGGER.info(
                "Loaded cached position: %.4f, %.4f (from %s)",
                cached["latitude"],
                cached["longitude"],
                cached.get("timestamp", "unknown"),
            )
            # Recompute time-dependent derived values from the cached raw data.
            data = self._compute_derived(cached)
            self._previous_data = data

    async def _save_cache(self, raw: dict[str, Any]) -> None:
        """Persist raw position data to disk for restart resilience."""
        # Store only the serialisable raw fields (no datetime objects).
        cache = {
            "latitude": raw.get("latitude"),
            "longitude": raw.get("longitude"),
            "speed": raw.get("speed"),
            "course": raw.get("course"),
            "heading": raw.get("heading"),
            "nav_status": raw.get("nav_status"),
            "timestamp": (
                raw["timestamp"].isoformat()
                if isinstance(raw.get("timestamp"), datetime)
                else raw.get("timestamp")
            ),
        }
        try:
            await self._store.async_save(cache)
        except Exception:
            _LOGGER.warning("Failed to save position cache", exc_info=True)

    async def _fetch_ais_data(self) -> dict[str, Any] | None:
        """Connect to AISStream WebSocket and fetch latest position report."""
        subscription = {
            "APIKey": self._api_key,
            "BoundingBoxes": [[[-90, -180], [90, 180]]],
            "FiltersShipMMSI": [TARA_MMSI],
            "FilterMessageTypes": ["PositionReport"],
        }

        session = aiohttp.ClientSession()
        try:
            async with asyncio.timeout(WS_TIMEOUT):
                ws = await session.ws_connect(AISSTREAM_WS_URL)
                try:
                    await ws.send_json(subscription)
                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            data = json.loads(msg.data)
                            if data.get("MessageType") == "PositionReport":
                                return self._parse_position(data)
                        elif msg.type in (
                            aiohttp.WSMsgType.ERROR,
                            aiohttp.WSMsgType.CLOSED,
                        ):
                            _LOGGER.warning(
                                "AIS WebSocket closed unexpectedly: %s", msg
                            )
                            break
                finally:
                    await ws.close()
        except TimeoutError:
            _LOGGER.debug(
                "AIS WebSocket timeout — no position report within %ds",
                WS_TIMEOUT,
            )
            return None
        except aiohttp.ClientError as err:
            _LOGGER.warning("AIS WebSocket connection error: %s", err)
            return None
        except Exception:
            _LOGGER.exception("Unexpected error fetching AIS data")
            return None
        finally:
            await session.close()

        return None

    @staticmethod
    def _parse_position(data: dict[str, Any]) -> dict[str, Any]:
        """Extract position fields from an AISStream PositionReport message."""
        meta = data.get("MetaData", {})
        report = data.get("Message", {}).get("PositionReport", {})

        return {
            "latitude": meta.get("latitude") or report.get("Latitude"),
            "longitude": meta.get("longitude") or report.get("Longitude"),
            "speed": report.get("Sog", 0.0),
            "course": report.get("Cog", 0.0),
            "heading": report.get("TrueHeading"),
            "nav_status": report.get("NavigationalStatus"),
            "timestamp": meta.get("time_utc"),
        }

    def _compute_derived(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Compute derived values from raw telemetry."""
        data = dict(raw)
        lat = raw.get("latitude")
        lon = raw.get("longitude")
        speed = raw.get("speed", 0.0)
        now = datetime.now(timezone.utc)

        # Parse timestamp
        data["timestamp"] = parse_ais_timestamp(raw.get("timestamp"))

        if lat is not None and lon is not None:
            # Distance metrics
            data["distance_from_home"] = round(
                haversine_distance(self._home_lat, self._home_lon, lat, lon),
                1,
            )
            data["distance_to_north_pole"] = round(
                haversine_distance(
                    lat, lon, NORTH_POLE_LATITUDE, NORTH_POLE_LONGITUDE
                ),
                1,
            )
            bearing = calculate_bearing(
                self._home_lat, self._home_lon, lat, lon
            )
            data["bearing_from_home"] = round(bearing, 1)
            data["bearing_compass"] = compass_direction(bearing)

            # Polar context
            data["in_arctic_circle"] = lat >= ARCTIC_CIRCLE_LATITUDE
            data["in_polar_day"] = is_polar_day(lat, lon, now)
            data["in_polar_night"] = is_polar_night(lat, lon, now)

            # Solar data
            data["solar_elevation"] = round(
                get_solar_elevation(lat, lon, now), 1
            )
            sr, ss = get_sunrise_sunset(lat, lon, now)
            data["local_sunrise"] = sr.isoformat() if sr else None
            data["local_sunset"] = ss.isoformat() if ss else None
        else:
            data["distance_from_home"] = None
            data["distance_to_north_pole"] = None
            data["bearing_from_home"] = None
            data["bearing_compass"] = None
            data["in_arctic_circle"] = False
            data["in_polar_day"] = False
            data["in_polar_night"] = False
            data["solar_elevation"] = None
            data["local_sunrise"] = None
            data["local_sunset"] = None

        # Stationary
        data["stationary"] = (speed or 0.0) < STATIONARY_SPEED_THRESHOLD

        # Expedition timeline
        try:
            departure = datetime.strptime(
                self._departure_date, "%Y-%m-%d"
            ).replace(tzinfo=timezone.utc)
            delta = now - departure
            data["days_since_departure"] = max(0, delta.days)
        except (ValueError, TypeError):
            data["days_since_departure"] = None

        # Mission phase
        if (
            data["days_since_departure"] is None
            or data["days_since_departure"] == 0
        ):
            data["mission_phase"] = "Pre-departure"
        elif data.get("stationary"):
            data["mission_phase"] = "Drifting"
        else:
            data["mission_phase"] = "Transit"

        return data

    def _fire_events(self, data: dict[str, Any]) -> None:
        """Fire Home Assistant events on state transitions."""
        event_payload = {
            "latitude": data.get("latitude"),
            "longitude": data.get("longitude"),
            "speed": data.get("speed"),
            "distance_to_pole": data.get("distance_to_north_pole"),
            "timestamp": (
                data["timestamp"].isoformat()
                if isinstance(data.get("timestamp"), datetime)
                else data.get("timestamp")
            ),
        }

        # Always fire position updated
        self.hass.bus.async_fire(EVENT_POSITION_UPDATED, event_payload)

        if self._previous_data is None:
            return

        prev = self._previous_data

        # Arctic circle transition
        if not prev.get("in_arctic_circle") and data.get("in_arctic_circle"):
            self.hass.bus.async_fire(EVENT_ENTERED_ARCTIC, event_payload)

        # Polar night transition
        if not prev.get("in_polar_night") and data.get("in_polar_night"):
            self.hass.bus.async_fire(
                EVENT_ENTERED_POLAR_NIGHT, event_payload
            )

        # Stationary transition
        if not prev.get("stationary") and data.get("stationary"):
            self.hass.bus.async_fire(EVENT_STATIONARY, event_payload)

        # Resumed transit
        if prev.get("stationary") and not data.get("stationary"):
            self.hass.bus.async_fire(EVENT_RESUMED_TRANSIT, event_payload)
