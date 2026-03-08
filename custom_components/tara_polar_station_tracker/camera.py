"""Camera platform for Tara Polar Station Tracker."""
from __future__ import annotations

import logging

import aiohttp

from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, PANOMAX_IMAGE_URL

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Tara Polar Station camera entity."""
    async_add_entities([TaraPolarStationCamera(entry)])


class TaraPolarStationCamera(Camera):
    """Representation of the Tara Polar Station Panomax webcam."""

    _attr_has_entity_name = True
    _attr_name = "Webcam"
    _attr_is_streaming = False
    _attr_is_on = True
    _attr_frame_interval = 300  # 5 minutes

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the camera."""
        super().__init__()
        self._attr_unique_id = f"{entry.entry_id}_webcam"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Tara Polar Station",
            manufacturer="Tara Ocean Foundation",
            model="Polar Station",
            entry_type=DeviceEntryType.SERVICE,
        )

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Fetch the latest webcam image from Panomax."""
        try:
            session = async_get_clientsession(self.hass)
            async with session.get(
                PANOMAX_IMAGE_URL,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status == 200:
                    return await resp.read()
                _LOGGER.warning(
                    "Failed to fetch webcam image: HTTP %s", resp.status
                )
        except (aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.warning("Error fetching webcam image: %s", err)
        return None
