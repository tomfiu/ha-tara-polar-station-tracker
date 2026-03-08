"""Utility functions for Tara Polar Station Tracker."""
from __future__ import annotations

import math
from datetime import datetime, timezone

from astral import LocationInfo
from astral.sun import elevation, sunrise, sunset


def haversine_distance(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """Calculate the great-circle distance in km between two points."""
    r = 6371.0  # Earth radius in km

    lat1_r = math.radians(lat1)
    lat2_r = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.asin(math.sqrt(a))

    return r * c


def calculate_bearing(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """Calculate initial bearing from point 1 to point 2 in degrees."""
    lat1_r = math.radians(lat1)
    lat2_r = math.radians(lat2)
    dlon_r = math.radians(lon2 - lon1)

    x = math.sin(dlon_r) * math.cos(lat2_r)
    y = math.cos(lat1_r) * math.sin(lat2_r) - math.sin(lat1_r) * math.cos(
        lat2_r
    ) * math.cos(dlon_r)

    bearing = math.degrees(math.atan2(x, y))
    return (bearing + 360) % 360


def compass_direction(bearing: float) -> str:
    """Convert bearing in degrees to a 16-point compass direction."""
    directions = [
        "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
        "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
    ]
    idx = round(bearing / 22.5) % 16
    return directions[idx]


def get_solar_elevation(
    latitude: float, longitude: float, dt: datetime | None = None
) -> float:
    """Get solar elevation angle at given coordinates and time."""
    if dt is None:
        dt = datetime.now(timezone.utc)

    loc = LocationInfo(latitude=latitude, longitude=longitude)
    return elevation(loc.observer, dt)


def get_sunrise_sunset(
    latitude: float, longitude: float, dt: datetime | None = None
) -> tuple[datetime | None, datetime | None]:
    """Get sunrise and sunset times. Returns None for components during polar day/night."""
    if dt is None:
        dt = datetime.now(timezone.utc)

    loc = LocationInfo(latitude=latitude, longitude=longitude)

    try:
        sr = sunrise(loc.observer, dt)
    except ValueError:
        sr = None

    try:
        ss = sunset(loc.observer, dt)
    except ValueError:
        ss = None

    return sr, ss


def is_polar_day(
    latitude: float, longitude: float, dt: datetime | None = None
) -> bool:
    """Check if location is experiencing polar day (sun never sets)."""
    sr, ss = get_sunrise_sunset(latitude, longitude, dt)
    if sr is None and ss is None:
        elev = get_solar_elevation(latitude, longitude, dt)
        return elev > 0
    if ss is None and sr is not None:
        return True
    return False


def is_polar_night(
    latitude: float, longitude: float, dt: datetime | None = None
) -> bool:
    """Check if location is experiencing polar night (sun never rises)."""
    sr, ss = get_sunrise_sunset(latitude, longitude, dt)
    if sr is None and ss is None:
        elev = get_solar_elevation(latitude, longitude, dt)
        return elev < 0
    if sr is None and ss is not None:
        return True
    return False


def parse_ais_timestamp(ts: str | None) -> datetime | None:
    """Parse AISStream timestamp into a timezone-aware datetime."""
    if ts is None:
        return None
    try:
        # AISStream format: "2026-03-08 12:00:00.000000 +0000 UTC"
        ts_clean = ts.replace(" UTC", "").strip()
        return datetime.strptime(ts_clean, "%Y-%m-%d %H:%M:%S.%f %z")
    except (ValueError, TypeError):
        pass
    try:
        return datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        pass
    return None
