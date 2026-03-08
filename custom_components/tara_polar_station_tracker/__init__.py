"""Tara Polar Station Tracker integration for Home Assistant."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import (
    CONF_API_KEY,
    CONF_DEPARTURE_DATE,
    CONF_ENABLE_WEBCAM,
    CONF_HOME_LAT,
    CONF_HOME_LON,
    CONF_POLL_INTERVAL,
    DEFAULT_DEPARTURE_DATE,
    DEFAULT_ENABLE_WEBCAM,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
)
from .coordinator import TaraPolarStationCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS_BASE: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Tara Polar Station from a config entry."""
    api_key = entry.data[CONF_API_KEY]

    poll_interval = entry.options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)
    home_lat = entry.options.get(CONF_HOME_LAT) or hass.config.latitude
    home_lon = entry.options.get(CONF_HOME_LON) or hass.config.longitude
    departure_date = entry.options.get(
        CONF_DEPARTURE_DATE, DEFAULT_DEPARTURE_DATE
    )
    enable_webcam = entry.options.get(CONF_ENABLE_WEBCAM, DEFAULT_ENABLE_WEBCAM)

    coordinator = TaraPolarStationCoordinator(
        hass, api_key, poll_interval, home_lat, home_lon, departure_date
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    platforms = list(PLATFORMS_BASE)
    if enable_webcam:
        platforms.append(Platform.CAMERA)

    await hass.config_entries.async_forward_entry_setups(entry, platforms)
    entry.async_on_unload(entry.add_update_listener(_async_update_options))

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
