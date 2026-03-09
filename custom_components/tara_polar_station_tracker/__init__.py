"""Tara Polar Station Tracker integration for Home Assistant."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import (
    CONF_API_KEY,
    CONF_DATA_SOURCE,
    CONF_DEPARTURE_DATE,
    CONF_ENABLE_WEBCAM,
    CONF_HOME_LAT,
    CONF_HOME_LON,
    CONF_POLL_INTERVAL,
    DEFAULT_DATA_SOURCE,
    DEFAULT_DEPARTURE_DATE,
    DEFAULT_ENABLE_WEBCAM,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    STORAGE_KEY,
    STORAGE_VERSION,
)
from .coordinator import TaraPolarStationCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS_BASE: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Tara Polar Station from a config entry."""
    api_key = entry.data[CONF_API_KEY]
    # Backward-compatible: entries created before multi-source support default
    # to AISStream so existing configurations continue to work unchanged.
    data_source = entry.data.get(CONF_DATA_SOURCE, DEFAULT_DATA_SOURCE)

    poll_interval = entry.options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)
    home_lat = entry.options.get(CONF_HOME_LAT) or hass.config.latitude
    home_lon = entry.options.get(CONF_HOME_LON) or hass.config.longitude
    departure_date = entry.options.get(
        CONF_DEPARTURE_DATE, DEFAULT_DEPARTURE_DATE
    )
    enable_webcam = entry.options.get(CONF_ENABLE_WEBCAM, DEFAULT_ENABLE_WEBCAM)

    store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}_{entry.entry_id}")
    coordinator = TaraPolarStationCoordinator(
        hass,
        api_key,
        poll_interval,
        home_lat,
        home_lon,
        departure_date,
        store,
        data_source=data_source,
    )

    # Store coordinator so platforms can access it during setup
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    platforms = list(PLATFORMS_BASE)
    if enable_webcam:
        platforms.append(Platform.CAMERA)

    # Set up platforms immediately — entities will show "Unknown" until
    # the first AIS report arrives.  We intentionally skip
    # async_config_entry_first_refresh() because the AIS WebSocket
    # fetch can take up to 90 s, which exceeds HA's 60 s setup timeout.
    await hass.config_entries.async_forward_entry_setups(entry, platforms)
    entry.async_on_unload(entry.add_update_listener(_async_update_options))

    # Kick off first data fetch in the background
    hass.async_create_task(coordinator.async_refresh())

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    enable_webcam = entry.options.get(CONF_ENABLE_WEBCAM, DEFAULT_ENABLE_WEBCAM)
    platforms = list(PLATFORMS_BASE)
    if enable_webcam:
        platforms.append(Platform.CAMERA)

    if await hass.config_entries.async_unload_platforms(entry, platforms):
        hass.data[DOMAIN].pop(entry.entry_id)
        return True
    return False


async def _async_update_options(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Handle options update by reloading the entry."""
    await hass.config_entries.async_reload(entry.entry_id)
