"""Constants for the Tara Polar Station Tracker integration."""
from __future__ import annotations

from typing import Final

DOMAIN: Final = "tara_polar_station_tracker"

CONF_API_KEY: Final = "api_key"
CONF_POLL_INTERVAL: Final = "poll_interval"
CONF_HOME_LAT: Final = "home_latitude"
CONF_HOME_LON: Final = "home_longitude"
CONF_ENABLE_WEBCAM: Final = "enable_webcam"
CONF_DEPARTURE_DATE: Final = "departure_date"

DEFAULT_POLL_INTERVAL: Final = 15  # minutes
DEFAULT_ENABLE_WEBCAM: Final = True
DEFAULT_DEPARTURE_DATE: Final = "2026-07-01"  # Planned first Arctic drift

TARA_MMSI: Final = "228471700"

AISSTREAM_WS_URL: Final = "wss://stream.aisstream.io/v0/stream"

PANOMAX_CAM_ID: Final = "10693"
PANOMAX_IMAGE_URL: Final = (
    f"https://live-image.panomax.com/cams/{PANOMAX_CAM_ID}/recent_reduced.jpg"
)

ARCTIC_CIRCLE_LATITUDE: Final = 66.5
NORTH_POLE_LATITUDE: Final = 90.0
NORTH_POLE_LONGITUDE: Final = 0.0
STATIONARY_SPEED_THRESHOLD: Final = 0.5  # knots

STORAGE_KEY: Final = DOMAIN
STORAGE_VERSION: Final = 1

FAST_POLL_INTERVAL: Final = 2  # minutes — used until first AIS data arrives

EVENT_POSITION_UPDATED: Final = f"{DOMAIN}_position_updated"
EVENT_ENTERED_ARCTIC: Final = f"{DOMAIN}_entered_arctic_circle"
EVENT_ENTERED_POLAR_NIGHT: Final = f"{DOMAIN}_entered_polar_night"
EVENT_STATIONARY: Final = f"{DOMAIN}_stationary"
EVENT_RESUMED_TRANSIT: Final = f"{DOMAIN}_resumed_transit"
